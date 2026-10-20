"""Recommendation logic over the precomputed model. Pure Python, no AWS/HTTP."""

from collections import defaultdict

NEUTRAL_RATING = 3.0  # ratings above this pull neighbours up, below push them down
POSTER_URL = "https://image.tmdb.org/t/p/w342"
BACKDROP_URL = "https://image.tmdb.org/t/p/w1280"


def _image(base, path):
    return base + path if path else None


class Recommender:
    def __init__(self, model):
        self._movies = {int(i): m for i, m in model["movies"].items()}
        self._neighbours = {int(i): n for i, n in model["neighbours"].items()}
        self._popular = list(model["popular"])

    def movie(self, movie_id):
        m = self._movies.get(movie_id)
        if m is None:
            return None
        return {
            "id": movie_id,
            "title": m["title"],
            "year": m["year"],
            "genres": m["genres"],
            "poster": _image(POSTER_URL, m.get("poster")),
        }

    def details(self, movie_id):
        """Everything the movie page shows. TMDB fields are null when unknown."""
        summary = self.movie(movie_id)
        if summary is None:
            return None
        m = self._movies[movie_id]
        return {
            **summary,
            "backdrop": _image(BACKDROP_URL, m.get("backdrop")),
            "overview": m.get("overview"),
            "tagline": m.get("tagline"),
            "runtime": m.get("runtime"),
            "director": m.get("director"),
            "cast": m.get("cast") or [],
            "avg": m.get("avg"),
            "count": m.get("count", 0),
        }

    def search(self, query, limit=20):
        query = query.strip().lower()
        if not query:
            return []
        hits = [i for i, m in self._movies.items() if query in m["title"].lower()]
        hits.sort(key=lambda i: -self._movies[i].get("count", 0))
        return [self.movie(i) for i in hits[:limit]]

    def popular(self, limit=20, exclude=()):
        ids = [i for i in self._popular if i not in exclude and i in self._movies]
        return [self.movie(i) for i in ids[:limit]]

    def similar(self, movie_id, limit=10):
        return [
            {**self.movie(n), "score": score}
            for n, score in self._neighbours.get(movie_id, [])[:limit]
        ]

    def recommend(self, ratings, limit=20, exclude=()):
        """Score each neighbour of a rated movie by sum(weight * similarity),
        where weight = rating - 3. Rated and `exclude`d movies are never
        recommended. Falls back to popular movies when the user has no positive
        signal yet."""
        skip = set(ratings) | set(exclude)
        scores = defaultdict(float)
        contributions = defaultdict(dict)  # candidate -> {rated movie: contribution}
        for rated_id, rating in ratings.items():
            weight = rating - NEUTRAL_RATING
            for n, similarity in self._neighbours.get(rated_id, []):
                scores[n] += weight * similarity
                contributions[n][rated_id] = weight * similarity

        candidates = [i for i, s in scores.items() if s > 0 and i not in skip]
        candidates.sort(key=lambda i: -scores[i])
        if not candidates:
            return [{**m, "score": None, "because": None} for m in self.popular(limit, exclude=skip)]

        results = []
        for i in candidates[:limit]:
            reason = max(contributions[i], key=contributions[i].get)
            results.append({**self.movie(i), "score": round(scores[i], 4), "because": self._movies[reason]["title"]})
        return results
