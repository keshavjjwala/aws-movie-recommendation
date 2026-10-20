import gzip
import json

import pandas as pd
import pytest

from train import build_model, save_model


@pytest.fixture
def frames():
    movies = pd.DataFrame(
        [
            (1, "Toy Story (1995)", "Animation|Comedy"),
            (2, "Shrek (2001)", "Animation|Comedy"),
            (3, "Alien (1979)", "Horror|Sci-Fi"),
            (4, "Aliens (1986)", "Horror|Sci-Fi"),
            (5, "Heat (1995)", "Crime|Thriller"),
            (6, "Untitled", "(no genres listed)"),
        ],
        columns=["movieId", "title", "genres"],
    )
    rows = []
    for user in range(12):
        fan_of_animation = user < 6
        rows += [
            (user, 1, 5.0 if fan_of_animation else 1.0),
            (user, 2, 5.0 if fan_of_animation else 1.0),
            (user, 3, 1.0 if fan_of_animation else 5.0),
            (user, 4, 1.0 if fan_of_animation else 5.0),
            (user, 5, 4.5),
        ]
    rows += [(100, 6, 5.0), (101, 6, 5.0)]
    ratings = pd.DataFrame(rows, columns=["userId", "movieId", "rating"])
    tags = pd.DataFrame(
        [(1, 3, "space"), (2, 4, "space")], columns=["userId", "movieId", "tag"]
    )
    return movies, ratings, tags


def test_parses_title_year_and_genres(frames):
    model = build_model(*frames)
    assert model["movies"]["1"]["title"] == "Toy Story"
    assert model["movies"]["1"]["year"] == 1995
    assert model["movies"]["1"]["genres"] == ["Animation", "Comedy"]
    assert model["movies"]["6"]["year"] is None
    assert model["movies"]["6"]["genres"] == []


def test_neighbours_exclude_self_and_respect_k(frames):
    model = build_model(*frames, k=2)
    for movie_id, neighbours in model["neighbours"].items():
        assert len(neighbours) <= 2
        assert int(movie_id) not in [n for n, _ in neighbours]


def test_most_similar_movie_shares_genre_and_audience(frames):
    model = build_model(*frames)
    assert model["neighbours"]["1"][0][0] == 2
    assert model["neighbours"]["3"][0][0] == 4


def test_movie_with_no_content_and_few_ratings_has_no_neighbours(frames):
    model = build_model(*frames)
    assert model["neighbours"]["6"] == []


def test_popular_uses_bayesian_average(frames):
    model = build_model(*frames)
    popular = model["popular"]
    assert popular[0] == 5  # 12 ratings of 4.5 beats 2 ratings of 5.0
    assert popular.index(5) < popular.index(6)


def test_save_model_writes_gzipped_json(frames, tmp_path):
    model = build_model(*frames)
    path = tmp_path / "model.json.gz"
    save_model(model, path)
    with gzip.open(path, "rt") as f:
        assert json.load(f) == model


def test_moves_trailing_article_to_front(frames):
    movies, ratings, tags = frames
    movies.loc[4, "title"] = "Matrix, The (1999)"
    model = build_model(movies, ratings, tags)
    assert model["movies"]["5"]["title"] == "The Matrix"
    assert model["movies"]["5"]["year"] == 1999


def test_shared_audience_beats_obscure_content_twin(frames):
    movies, ratings, tags = frames
    obscure_twin = pd.DataFrame([(7, "Clone (2010)", "Animation|Comedy")], columns=movies.columns)
    movies = pd.concat([movies, obscure_twin], ignore_index=True)
    ratings = pd.concat(
        [ratings, pd.DataFrame([(200, 7, 4.0)], columns=ratings.columns)], ignore_index=True
    )
    scores = dict(build_model(movies, ratings, tags)["neighbours"]["1"])
    assert scores[2] > scores[7]


def test_stores_rating_count_per_movie(frames):
    model = build_model(*frames)
    assert model["movies"]["1"]["count"] == 12
    assert model["movies"]["6"]["count"] == 2


def test_stores_average_rating_rounded(frames):
    model = build_model(*frames)
    assert model["movies"]["5"]["avg"] == 4.5
    assert model["movies"]["1"]["avg"] == 3.0


def test_merges_tmdb_details_when_given(frames):
    details = {
        1: {"movieId": 1, "poster": "/toy.jpg", "backdrop": "/toy-wide.jpg", "overview": "Toys.",
            "tagline": None, "runtime": 81, "director": "John Lasseter", "cast": ["Tom Hanks"]},
    }
    model = build_model(*frames, details=details)
    toy = model["movies"]["1"]
    assert toy["poster"] == "/toy.jpg" and toy["runtime"] == 81 and toy["cast"] == ["Tom Hanks"]
    assert "movieId" not in toy
    assert "poster" not in model["movies"]["2"]


def test_load_details_reads_jsonl(tmp_path):
    from train import load_details

    path = tmp_path / "tmdb.jsonl"
    path.write_text('{"movieId": 1, "poster": "/a.jpg"}\n{"movieId": 2, "poster": null}\n')
    assert load_details(path) == {1: {"movieId": 1, "poster": "/a.jpg"}, 2: {"movieId": 2, "poster": None}}
    assert load_details(tmp_path / "missing.jsonl") == {}
