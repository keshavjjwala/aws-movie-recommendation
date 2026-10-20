from app.recommender import Recommender


def titles(movies):
    return [m["title"] for m in movies]


def test_movie_returns_metadata_with_id(tiny_model):
    rec = Recommender(tiny_model)
    assert rec.movie(3) == {
        "id": 3, "title": "Alien", "year": 1979, "genres": ["Horror", "Sci-Fi"],
        "poster": "https://image.tmdb.org/t/p/w342/alien.jpg",
    }
    assert rec.movie(999) is None


def test_search_is_case_insensitive_and_ranked_by_rating_count(tiny_model):
    rec = Recommender(tiny_model)
    assert titles(rec.search("STORY")) == ["Toy Story", "Toy Story 2", "Mr. (Unknown) Story*"]


def test_search_treats_special_characters_literally(tiny_model):
    rec = Recommender(tiny_model)
    assert titles(rec.search("(unknown)")) == ["Mr. (Unknown) Story*"]
    assert rec.search("*") != [] and rec.search("[") == []


def test_search_with_blank_query_returns_nothing(tiny_model):
    assert Recommender(tiny_model).search("   ") == []


def test_search_respects_limit(tiny_model):
    assert len(Recommender(tiny_model).search("o", limit=2)) == 2


def test_popular_keeps_model_order(tiny_model):
    assert [m["id"] for m in Recommender(tiny_model).popular(limit=3)] == [5, 1, 3]


def test_similar_returns_neighbours_with_scores(tiny_model):
    similar = Recommender(tiny_model).similar(3)
    assert [(m["id"], m["score"]) for m in similar] == [(4, 0.8), (5, 0.2)]


def test_similar_of_unknown_movie_is_empty(tiny_model):
    assert Recommender(tiny_model).similar(999) == []


def test_recommend_excludes_already_rated_movies(tiny_model):
    recs = Recommender(tiny_model).recommend({1: 5.0, 2: 5.0})
    assert 1 not in [m["id"] for m in recs] and 2 not in [m["id"] for m in recs]


def test_recommend_weights_by_rating_above_three(tiny_model):
    # Loving Alien (weight +2) outweighs liking Toy Story (weight +1).
    recs = Recommender(tiny_model).recommend({3: 5.0, 1: 4.0})
    assert [m["id"] for m in recs][:2] == [4, 2]
    assert recs[0]["score"] == 1.6  # 2 * 0.8


def test_recommend_explains_with_top_contributing_movie(tiny_model):
    recs = Recommender(tiny_model).recommend({3: 5.0, 1: 4.0})
    by_id = {m["id"]: m for m in recs}
    assert by_id[4]["because"] == "Alien"
    assert by_id[5]["because"] == "Alien"  # 2*0.2 from Alien beats 1*0.1 from Toy Story


def test_disliked_movies_push_neighbours_down(tiny_model):
    # Heat is a neighbour of both; hating Alien should cancel liking Toy Story.
    recs = Recommender(tiny_model).recommend({1: 4.0, 3: 1.0})
    assert 5 not in [m["id"] for m in recs]


def test_only_low_ratings_fall_back_to_popular(tiny_model):
    recs = Recommender(tiny_model).recommend({5: 2.0})
    assert [m["id"] for m in recs] == [1, 3, 2, 4]
    assert all(m["because"] is None for m in recs)


def test_no_ratings_returns_popular(tiny_model):
    assert [m["id"] for m in Recommender(tiny_model).recommend({}, limit=2)] == [5, 1]


def test_ratings_for_unknown_movies_are_ignored(tiny_model):
    recs = Recommender(tiny_model).recommend({999: 5.0})
    assert [m["id"] for m in recs][:1] == [5]


def test_movie_without_tmdb_poster_has_null_poster(tiny_model):
    assert Recommender(tiny_model).movie(4)["poster"] is None


def test_details_include_tmdb_fields_and_image_urls(tiny_model):
    details = Recommender(tiny_model).details(3)
    assert details["backdrop"] == "https://image.tmdb.org/t/p/w1280/alien-wide.jpg"
    assert details["director"] == "Ridley Scott"
    assert details["cast"] == ["Sigourney Weaver", "Tom Skerritt"]
    assert details["runtime"] == 117 and details["avg"] == 4.1 and details["count"] == 120
    assert details["tagline"] == "In space no one can hear you scream."


def test_details_without_tmdb_data_are_null(tiny_model):
    details = Recommender(tiny_model).details(4)
    assert details["title"] == "Aliens"
    for key in ("poster", "backdrop", "overview", "tagline", "runtime", "director", "avg"):
        assert details[key] is None, key
    assert details["cast"] == []


def test_details_of_unknown_movie_is_none(tiny_model):
    assert Recommender(tiny_model).details(999) is None


def test_recommend_also_excludes_given_movies(tiny_model):
    rec = Recommender(tiny_model)
    assert 4 not in [m["id"] for m in rec.recommend({3: 5.0}, exclude={4})]


def test_popular_fallback_respects_exclude(tiny_model):
    rec = Recommender(tiny_model)
    assert [m["id"] for m in rec.recommend({}, limit=3, exclude={5, 1})] == [3, 2, 4]
