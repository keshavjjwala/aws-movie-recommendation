from app.library import stats, taste
from app.recommender import Recommender


def e(status, rating=None):
    return {"status": status, "rating": rating, "updated": "2026-10-18T10:00:00+00:00"}


def test_taste_uses_ratings():
    assert taste({1: e("watched", 4.5), 2: e("watching")}) == {1: 4.5}


def test_dropped_without_rating_counts_as_a_dislike():
    assert taste({1: e("dropped"), 2: e("dropped", 4.0)}) == {1: 2.0, 2: 4.0}


def test_stats_for_empty_library(tiny_model):
    assert stats({}, Recommender(tiny_model)) == {
        "counts": {"plan_to_watch": 0, "watching": 0, "watched": 0, "dropped": 0},
        "rated": 0,
        "averageRating": None,
        "minutesWatched": 0,
        "topGenres": [],
    }


def test_stats_summarise_the_library(tiny_model):
    library = {
        3: e("watched", 5.0),          # Alien: 117 min, Horror/Sci-Fi
        4: e("watched", 4.0),          # Aliens: no runtime known
        1: e("watched"),               # Toy Story: Animation/Comedy
        2: e("plan_to_watch"),
        5: e("dropped", 1.5),
        999: e("watched", 3.0),        # not in the model: ignored
    }
    result = stats(library, Recommender(tiny_model))
    assert result["counts"] == {"plan_to_watch": 1, "watching": 0, "watched": 3, "dropped": 1}
    assert result["rated"] == 3
    assert result["averageRating"] == 3.5
    assert result["minutesWatched"] == 117
    assert result["topGenres"][:2] == [{"genre": "Horror", "count": 2}, {"genre": "Sci-Fi", "count": 2}]
    assert len(result["topGenres"]) == 3
