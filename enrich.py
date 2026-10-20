"""Fetches posters and details for every MovieLens movie from TMDB.

Writes data/tmdb.jsonl (one JSON record per movie), which train.py merges into
the model. Only this offline script uses the TMDB key: it never reaches the
browser, the Lambda function or git.

Usage:
    echo 'TMDB_API_KEY=...' > .env     # v3 "API Key" or v4 "Read Access Token"
    python enrich.py                   # ~3 minutes; safe to interrupt and rerun
    python train.py                    # rebuild the model with the new data
"""

import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

LINKS = Path("data/ml-latest-small/links.csv")
OUTPUT = Path("data/tmdb.jsonl")
API = "https://api.themoviedb.org/3/movie/"
MAX_ERRORS = 3
MAX_RATE_LIMIT_WAITS = 10


class FetchError(Exception):
    pass


def load_key(env_file=Path(".env")):
    if os.environ.get("TMDB_API_KEY"):
        return os.environ["TMDB_API_KEY"]
    try:
        lines = Path(env_file).read_text().splitlines()
    except FileNotFoundError:
        return None
    for line in lines:
        name, _, value = line.partition("=")
        if name.strip() == "TMDB_API_KEY":
            return value.strip().strip("\"'") or None
    return None


def make_fetch(key, opener=urllib.request.urlopen, sleep=time.sleep):
    """Returns fetch(tmdb_id) -> TMDB movie JSON, or None if TMDB doesn't know it."""
    is_token = key.startswith("eyJ")  # v4 read access tokens are JWTs

    def fetch(tmdb_id):
        params = {"append_to_response": "credits"}
        if not is_token:
            params["api_key"] = key
        request = urllib.request.Request(f"{API}{tmdb_id}?{urllib.parse.urlencode(params)}")
        request.add_header("Accept", "application/json")
        if is_token:
            request.add_header("Authorization", f"Bearer {key}")

        errors = waits = 0
        while True:
            try:
                with opener(request, timeout=10) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return None
                if error.code == 429 and waits < MAX_RATE_LIMIT_WAITS:
                    waits += 1
                    sleep(float(error.headers.get("Retry-After") or 2))
                    continue
                if error.code == 401:
                    raise SystemExit("TMDB rejected the key (401). Check TMDB_API_KEY in .env.") from error
                last = error
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
                last = error
            errors += 1
            if errors >= MAX_ERRORS:
                raise FetchError(f"TMDB movie {tmdb_id}: {last}")
            sleep(1)

    return fetch


def parse_movie(movie_id, data):
    data = data or {}
    credits = data.get("credits") or {}
    director = next((c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"), None)
    cast = sorted(credits.get("cast", []), key=lambda c: c.get("order", 999))
    return {
        "movieId": movie_id,
        "poster": data.get("poster_path") or None,
        "backdrop": data.get("backdrop_path") or None,
        "overview": data.get("overview") or None,
        "tagline": data.get("tagline") or None,
        "runtime": data.get("runtime") or None,
        "director": director,
        "cast": [c["name"] for c in cast[:5]],
    }


def _done_ids(path):
    if not path.exists():
        return set()
    return {json.loads(line)["movieId"] for line in path.read_text().splitlines() if line.strip()}


def enrich(links, out_path, fetch, workers=8):
    """links: [(movieId, tmdbId or None)]. Appends records for movies not yet
    in out_path. Movies that keep failing are left out so a rerun retries them."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = _done_ids(out_path)
    todo = [(m, t) for m, t in links if m not in done]
    stats = {"skipped": len(links) - len(todo), "fetched": 0, "unknown": 0, "failed": 0}

    with out_path.open("a") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        def write(record):
            out.write(json.dumps(record) + "\n")
            stats["fetched" if record["poster"] or record["overview"] else "unknown"] += 1

        futures = {}
        for movie_id, tmdb_id in todo:
            if tmdb_id is None:
                write(parse_movie(movie_id, None))
            else:
                futures[pool.submit(fetch, tmdb_id)] = movie_id
        for n, future in enumerate(as_completed(futures), 1):
            try:
                write(parse_movie(futures[future], future.result()))
            except FetchError as error:
                stats["failed"] += 1
                print(f"  skipped: {error}")
            if n % 500 == 0:
                out.flush()
                print(f"  {n}/{len(futures)} fetched")
    return stats


def check_key(fetch):
    """One request up front, so a wrong key fails fast instead of 9,700 times."""
    fetch(862)  # Toy Story


def read_links(path=LINKS):
    with open(path, newline="") as f:
        return [
            (int(row["movieId"]), int(row["tmdbId"]) if row["tmdbId"].strip() else None)
            for row in csv.DictReader(f)
        ]


def main():
    key = load_key()
    if not key:
        raise SystemExit("No TMDB key. Put TMDB_API_KEY=... in .env (see .env.example).")
    if not LINKS.exists():
        raise SystemExit(f"{LINKS} not found. Run `python train.py` once first to download MovieLens.")
    links = read_links()
    print(f"Fetching TMDB details for {len(links)} movies (already done ones are skipped) ...")
    fetch = make_fetch(key)
    check_key(fetch)
    stats = enrich(links, OUTPUT, fetch)
    print(f"Done: {stats}. Now rebuild the model: python train.py")
    if stats["failed"]:
        print("Some movies failed; rerun `python enrich.py` to retry just those.")


if __name__ == "__main__":
    main()
