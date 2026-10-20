"""Turning a user's library (statuses + ratings) into recommendation input and
profile stats. Pure Python, no AWS/HTTP."""

from collections import Counter

from app.storage import STATUSES

DROPPED_RATING = 2.0  # a dropped movie you didn't rate counts as a mild dislike


def taste(library):
    """{movie_id: rating} for the recommender."""
    ratings = {}
    for movie_id, entry in library.items():
        if entry["rating"] is not None:
            ratings[movie_id] = entry["rating"]
        elif entry["status"] == "dropped":
            ratings[movie_id] = DROPPED_RATING
    return ratings


def stats(library, recommender):
    library = {i: e for i, e in library.items() if recommender.movie(i)}
    counts = Counter(e["status"] for e in library.values())
    ratings = [e["rating"] for e in library.values() if e["rating"] is not None]
    watched = [recommender.details(i) for i, e in library.items() if e["status"] == "watched"]
    genres = Counter(g for m in watched for g in m["genres"])
    return {
        "counts": {s: counts.get(s, 0) for s in STATUSES},
        "rated": len(ratings),
        "averageRating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "minutesWatched": sum(m["runtime"] or 0 for m in watched),
        "topGenres": [{"genre": g, "count": n} for g, n in genres.most_common(3)],
    }
