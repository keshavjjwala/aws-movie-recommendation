import pytest
from moto import mock_aws

from app.storage import LibraryStore, StoreUnavailable


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        store = LibraryStore("Library")
        store.ensure_table()
        yield store


def entry(store, user, movie_id):
    return store.get_library(user).get(movie_id)


def test_new_user_has_empty_library(store):
    assert store.get_library("alice") == {}
    assert store.get_ratings("alice") == {}


def test_rating_an_unlisted_movie_marks_it_watched(store):
    store.set_rating("alice", 1, 4.5)
    e = entry(store, "alice", 1)
    assert (e["status"], e["rating"]) == ("watched", 4.5)
    assert isinstance(e["rating"], float) and e["updated"]


def test_rating_keeps_an_existing_status(store):
    store.set_status("alice", 1, "watching")
    store.set_rating("alice", 1, 3.0)
    assert entry(store, "alice", 1)["status"] == "watching"


def test_rating_a_planned_movie_moves_it_to_watched(store):
    store.set_status("alice", 1, "plan_to_watch")
    store.set_rating("alice", 1, 4.0)
    assert entry(store, "alice", 1)["status"] == "watched"


def test_status_change_keeps_rating(store):
    store.set_rating("alice", 1, 5.0)
    store.set_status("alice", 1, "dropped")
    e = entry(store, "alice", 1)
    assert (e["status"], e["rating"]) == ("dropped", 5.0)


def test_listed_without_rating_has_null_rating(store):
    store.set_status("alice", 7, "plan_to_watch")
    assert entry(store, "alice", 7)["rating"] is None
    assert store.get_ratings("alice") == {}


def test_clear_rating_keeps_status(store):
    store.set_rating("alice", 1, 5.0)
    store.clear_rating("alice", 1)
    e = entry(store, "alice", 1)
    assert (e["status"], e["rating"]) == ("watched", None)


def test_clear_rating_of_missing_entry_is_a_no_op(store):
    store.clear_rating("alice", 1)
    assert store.get_library("alice") == {}


def test_remove_deletes_the_entry(store):
    store.set_rating("alice", 1, 5.0)
    store.set_status("alice", 2, "watching")
    store.remove("alice", 1)
    assert list(store.get_library("alice")) == [2]


def test_get_ratings_returns_only_rated_movies(store):
    store.set_rating("alice", 1, 4.5)
    store.set_rating("alice", 42, 2.0)
    store.set_status("alice", 9, "watching")
    assert store.get_ratings("alice") == {1: 4.5, 42: 2.0}


def test_rating_again_overwrites(store):
    store.set_rating("alice", 1, 2.0)
    store.set_rating("alice", 1, 5.0)
    assert store.get_ratings("alice") == {1: 5.0}


def test_users_are_isolated(store):
    store.set_rating("alice", 1, 5.0)
    store.set_status("bob", 2, "watching")
    assert list(store.get_library("bob")) == [2]


def test_ensure_table_is_idempotent(store):
    store.ensure_table()
    store.set_rating("alice", 1, 5.0)
    assert store.get_ratings("alice") == {1: 5.0}


def test_unreachable_endpoint_raises_store_unavailable(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    store = LibraryStore("Library", endpoint_url="http://127.0.0.1:1")
    for call in (
        lambda: store.get_library("alice"),
        lambda: store.set_rating("alice", 1, 5.0),
        lambda: store.set_status("alice", 1, "watched"),
        lambda: store.clear_rating("alice", 1),
        lambda: store.remove("alice", 1),
    ):
        with pytest.raises(StoreUnavailable):
            call()
