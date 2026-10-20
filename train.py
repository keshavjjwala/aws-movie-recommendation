"""Offline model builder.

Downloads the MovieLens "ml-latest-small" dataset, computes a hybrid
(content + collaborative) item-item similarity, keeps the top-k neighbours of
every movie and writes the result as gzipped JSON. The API only ever reads that
small JSON file, so it needs no numpy/pandas/scikit-learn at runtime.

Usage:
    python train.py                              # writes model/model.json.gz
    python train.py --upload s3://bucket/key     # ...and uploads it to S3
"""

import argparse
import gzip
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

DATASET_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
DATA_DIR = Path("data")
DEFAULT_OUTPUT = Path("model/model.json.gz")
TMDB_DETAILS = DATA_DIR / "tmdb.jsonl"  # optional, written by enrich.py

MIN_RATINGS = 10  # movies need this many ratings to take part in collaborative filtering
CHUNK = 1000  # rows of the similarity matrix computed at once (keeps memory low)

TITLE_YEAR = re.compile(r"^(.*?)\s*\((\d{4})\)\s*$")
TRAILING_ARTICLE = re.compile(r"^(.*), (The|A|An)$")


def parse_title(raw):
    match = TITLE_YEAR.match(raw)
    title, year = (match.group(1), int(match.group(2))) if match else (raw.strip(), None)
    article = TRAILING_ARTICLE.match(title)
    if article:
        title = f"{article.group(2)} {article.group(1)}"
    return title, year


def parse_genres(raw):
    return [] if raw == "(no genres listed)" else raw.split("|")


def _token(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def content_matrix(movies, tags):
    """TF-IDF over genres + user tags, one L2-normalised row per movie."""
    tag_text = (
        tags.assign(tag=tags["tag"].astype(str).map(_token))
        .groupby("movieId")["tag"]
        .apply(" ".join)
    )
    docs = [
        " ".join(["genre_" + _token(g) for g in parse_genres(genres)])
        + " "
        + tag_text.get(movie_id, "")
        for movie_id, genres in zip(movies["movieId"], movies["genres"])
    ]
    vectorizer = TfidfVectorizer(token_pattern=r"[^ ]+")
    return vectorizer.fit_transform(docs)  # rows are already L2-normalised


def collaborative_matrix(movies, ratings, min_ratings):
    """Mean-centred, L2-normalised item x user matrix. Rows of movies with too
    few ratings are left empty."""
    index = {movie_id: i for i, movie_id in enumerate(movies["movieId"])}
    ratings = ratings[ratings["movieId"].isin(index)]
    counts = ratings["movieId"].value_counts()
    eligible_ids = set(counts[counts >= min_ratings].index)

    rated = ratings[ratings["movieId"].isin(eligible_ids)]
    users = {u: j for j, u in enumerate(rated["userId"].unique())}
    centred = rated["rating"] - rated.groupby("userId")["rating"].transform("mean")
    matrix = sparse.csr_matrix(
        (
            centred.to_numpy(),
            (rated["movieId"].map(index).to_numpy(), rated["userId"].map(users).to_numpy()),
        ),
        shape=(len(movies), max(len(users), 1)),
    )
    return normalize(matrix)


def top_neighbours(content, collab, k):
    """Hybrid similarity, computed in row chunks; returns top-k (id_index, score)."""
    n = content.shape[0]
    result = []
    for start in range(0, n, CHUNK):
        stop = min(start + CHUNK, n)
        c = (content[start:stop] @ content.T).toarray()
        k_sim = (collab[start:stop] @ collab.T).toarray()
        # Collaborative similarity is simply 0 where a movie has too few ratings,
        # so well-known films prefer neighbours that share an actual audience.
        scores = 0.5 * c + 0.5 * k_sim
        scores[np.arange(stop - start), np.arange(start, stop)] = -np.inf  # not yourself
        for row in scores:
            top = np.argsort(-row)[:k]
            result.append([(int(j), float(row[j])) for j in top if row[j] > 0])
    return result


def popular_movies(movies, ratings, n_popular, min_ratings):
    """Bayesian-weighted average: films with few ratings are pulled to the mean."""
    stats = ratings.groupby("movieId")["rating"].agg(["mean", "count"])
    stats = stats[stats.index.isin(movies["movieId"])]
    global_mean = ratings["rating"].mean()
    v, m = stats["count"], min_ratings
    weighted = v / (v + m) * stats["mean"] + m / (v + m) * global_mean
    return [int(i) for i in weighted.sort_values(ascending=False).index[:n_popular]]


def build_model(movies, ratings, tags, k=30, n_popular=50, min_ratings=MIN_RATINGS, details=None):
    """details: optional {movieId: TMDB record} from enrich.py, merged into each movie."""
    movies = movies.reset_index(drop=True)
    ids = movies["movieId"].astype(int).tolist()

    content = content_matrix(movies, tags)
    collab = collaborative_matrix(movies, ratings, min_ratings)
    neighbours = top_neighbours(content, collab, k)

    counts = ratings["movieId"].value_counts()
    averages = ratings.groupby("movieId")["rating"].mean()
    details = details or {}
    model_movies = {}
    for movie_id, raw_title, genres in zip(ids, movies["title"], movies["genres"]):
        title, year = parse_title(raw_title)
        model_movies[str(movie_id)] = {
            "title": title,
            "year": year,
            "genres": parse_genres(genres),
            "count": int(counts.get(movie_id, 0)),
            "avg": round(float(averages[movie_id]), 1) if movie_id in averages.index else None,
        }
        extra = details.get(movie_id)
        if extra:
            model_movies[str(movie_id)].update({k: v for k, v in extra.items() if k != "movieId"})

    return {
        "movies": model_movies,
        "neighbours": {
            str(ids[i]): [[ids[j], round(score, 4)] for j, score in row]
            for i, row in enumerate(neighbours)
        },
        "popular": popular_movies(movies, ratings, n_popular, min_ratings),
    }


def load_details(path=TMDB_DETAILS):
    """Reads data/tmdb.jsonl written by enrich.py; {} if it hasn't been run."""
    path = Path(path)
    if not path.exists():
        return {}
    records = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return {r["movieId"]: r for r in records}


def save_model(model, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(model, f, separators=(",", ":"))


def load_dataset(data_dir=DATA_DIR):
    folder = data_dir / "ml-latest-small"
    if not folder.exists():
        print(f"Downloading {DATASET_URL} ...")
        with urllib.request.urlopen(DATASET_URL) as response:
            zipfile.ZipFile(io.BytesIO(response.read())).extractall(data_dir)
    read = lambda name: pd.read_csv(folder / name)  # noqa: E731
    return read("movies.csv"), read("ratings.csv"), read("tags.csv")


def upload(path, s3_uri):
    import boto3

    bucket, _, key = s3_uri.removeprefix("s3://").partition("/")
    boto3.client("s3").upload_file(str(path), bucket, key or path.name)
    print(f"Uploaded to s3://{bucket}/{key or path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--upload", metavar="S3_URI", help="e.g. s3://my-bucket/model.json.gz")
    args = parser.parse_args()

    movies, ratings, tags = load_dataset()
    print(f"Building model from {len(movies)} movies and {len(ratings)} ratings ...")
    details = load_details()
    print(f"TMDB details: {len(details)} movies" if details else "TMDB details: none (run enrich.py for posters)")
    model = build_model(movies, ratings, tags, details=details)
    save_model(model, args.output)
    size_kb = args.output.stat().st_size / 1024
    print(f"Wrote {args.output} ({size_kb:.0f} KB)")
    if args.upload:
        upload(args.output, args.upload)


if __name__ == "__main__":
    main()
