import pytest


def movie(title, year, genres, count):
    return {"title": title, "year": year, "genres": genres, "count": count}


@pytest.fixture
def tiny_model():
    """Hand-built model: two animated films, two sci-fi horrors, one crime film."""
    return {
        "movies": {
            "1": movie("Toy Story", 1995, ["Animation", "Comedy"], 200),
            "2": movie("Toy Story 2", 1999, ["Animation", "Comedy"], 150),
            "3": {
                **movie("Alien", 1979, ["Horror", "Sci-Fi"], 120),
                "avg": 4.1,
                "poster": "/alien.jpg",
                "backdrop": "/alien-wide.jpg",
                "overview": "A crew meets a creature.",
                "tagline": "In space no one can hear you scream.",
                "runtime": 117,
                "director": "Ridley Scott",
                "cast": ["Sigourney Weaver", "Tom Skerritt"],
            },
            "4": movie("Aliens", 1986, ["Horror", "Sci-Fi"], 100),
            "5": movie("Heat", 1995, ["Crime"], 80),
            "6": movie("Mr. (Unknown) Story*", None, [], 1),
        },
        "neighbours": {
            "1": [[2, 0.9], [5, 0.1]],
            "2": [[1, 0.9]],
            "3": [[4, 0.8], [5, 0.2]],
            "4": [[3, 0.8]],
            "5": [[3, 0.2], [1, 0.1]],
            "6": [],
        },
        "popular": [5, 1, 3, 2, 4],
    }
