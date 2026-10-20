import json

import pytest
from fastapi.testclient import TestClient
from mangum import Mangum
from moto import mock_aws

from app.auth import CognitoAuth, LocalAuth
from app.main import create_app
from app.recommender import Recommender
from app.storage import LibraryStore, StoreUnavailable


@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        yield


@pytest.fixture
def store(aws_env):
    store = LibraryStore("Library")
    store.ensure_table()
    return store


@pytest.fixture
def auth(aws_env):
    auth = LocalAuth("LocalUsers", secret="test-secret")
    auth.ensure_table()
    return auth


@pytest.fixture
def client(tiny_model, store, auth):
    return TestClient(create_app(Recommender(tiny_model), store, auth))


@pytest.fixture
def alice(client):
    """Headers of a signed-in user."""
    token = client.post("/api/auth/local/signup", json={"email": "alice@example.com", "password": "correct horse"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def ids(response):
    return [m["id"] for m in response.json()]


# --- public movie endpoints -------------------------------------------------

def test_search(client):
    response = client.get("/api/movies/search", params={"q": "alien"})
    assert response.status_code == 200
    assert ids(response) == [3, 4]


def test_search_requires_query(client):
    assert client.get("/api/movies/search").status_code == 422


def test_popular_with_limit(client):
    assert ids(client.get("/api/movies/popular", params={"limit": 2})) == [5, 1]


def test_limit_out_of_range_is_rejected(client):
    assert client.get("/api/movies/popular", params={"limit": 0}).status_code == 422
    assert client.get("/api/movies/popular", params={"limit": 101}).status_code == 422


def test_similar(client):
    response = client.get("/api/movies/3/similar")
    assert response.status_code == 200
    assert response.json()[0] == {
        "id": 4, "title": "Aliens", "year": 1986, "genres": ["Horror", "Sci-Fi"], "poster": None, "score": 0.8,
    }


def test_similar_unknown_movie_is_404(client):
    assert client.get("/api/movies/999/similar").status_code == 404


def test_movie_details(client):
    response = client.get("/api/movies/3")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Alien" and body["director"] == "Ridley Scott"
    assert body["poster"].endswith("/w342/alien.jpg") and body["backdrop"].endswith("/w1280/alien-wide.jpg")


def test_movie_details_unknown_is_404(client):
    assert client.get("/api/movies/999").status_code == 404


def test_search_route_still_wins_over_details_route(client):
    assert client.get("/api/movies/search", params={"q": "heat"}).json()[0]["id"] == 5


# --- local accounts ----------------------------------------------------------

def test_sign_up_then_log_in(client):
    created = client.post("/api/auth/local/signup", json={"email": "Bob@example.com", "password": "hunter2hunter2"})
    assert created.status_code == 201 and created.json()["email"] == "bob@example.com"
    login = client.post("/api/auth/local/login", json={"email": "bob@example.com", "password": "hunter2hunter2"})
    assert login.status_code == 200 and login.json()["token"]


def test_wrong_password_is_401_with_message(client, alice):
    response = client.post("/api/auth/local/login", json={"email": "alice@example.com", "password": "nope nope"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong email or password."


def test_duplicate_sign_up_is_409(client, alice):
    response = client.post("/api/auth/local/signup", json={"email": "alice@example.com", "password": "correct horse"})
    assert response.status_code == 409


def test_short_password_is_422_with_message(client):
    response = client.post("/api/auth/local/signup", json={"email": "c@example.com", "password": "short"})
    assert response.status_code == 422 and "8 characters" in response.json()["detail"]


# --- the signed-in user's library --------------------------------------------

ME_REQUESTS = [
    ("get", "/api/me/library", None),
    ("put", "/api/me/library/3/status", {"status": "watching"}),
    ("put", "/api/me/library/3/rating", {"rating": 4}),
    ("delete", "/api/me/library/3/rating", None),
    ("delete", "/api/me/library/3", None),
    ("get", "/api/me/recommendations", None),
    ("get", "/api/me/stats", None),
]


@pytest.mark.parametrize("method,path,body", ME_REQUESTS)
def test_me_endpoints_need_sign_in(client, method, path, body):
    kwargs = {"json": body} if body else {}
    for headers in ({}, {"Authorization": "Bearer forged.token"}):
        response = client.request(method, path, headers=headers, **kwargs)
        assert response.status_code == 401
        assert response.json()["detail"] == "Sign in to use your list."


def test_rate_then_library_shows_watched_with_rating(client, alice):
    response = client.put("/api/me/library/3/rating", json={"rating": 4.5}, headers=alice)
    assert response.status_code == 200 and response.json() == {"movieId": 3, "rating": 4.5}
    [entry] = client.get("/api/me/library", headers=alice).json()
    assert (entry["id"], entry["title"], entry["status"], entry["rating"]) == (3, "Alien", "watched", 4.5)
    assert entry["poster"] == "https://image.tmdb.org/t/p/w342/alien.jpg"


def test_set_status_then_change_it(client, alice):
    assert client.put("/api/me/library/2/status", json={"status": "plan_to_watch"}, headers=alice).status_code == 200
    client.put("/api/me/library/2/status", json={"status": "watching"}, headers=alice)
    [entry] = client.get("/api/me/library", headers=alice).json()
    assert (entry["status"], entry["rating"]) == ("watching", None)


@pytest.mark.parametrize("status", ["finished", "", None, "WATCHED"])
def test_invalid_status_is_422(client, alice, status):
    assert client.put("/api/me/library/2/status", json={"status": status}, headers=alice).status_code == 422


@pytest.mark.parametrize("rating", [0, 0.4, 5.5, "great", None])
def test_invalid_rating_is_422(client, alice, rating):
    assert client.put("/api/me/library/3/rating", json={"rating": rating}, headers=alice).status_code == 422


def test_unknown_movie_is_404_and_not_stored(client, alice, store):
    assert client.put("/api/me/library/999/rating", json={"rating": 4}, headers=alice).status_code == 404
    assert client.put("/api/me/library/999/status", json={"status": "watching"}, headers=alice).status_code == 404
    assert client.get("/api/me/library", headers=alice).json() == []


def test_clear_rating_keeps_movie_on_list(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 5}, headers=alice)
    assert client.delete("/api/me/library/3/rating", headers=alice).status_code == 204
    [entry] = client.get("/api/me/library", headers=alice).json()
    assert (entry["status"], entry["rating"]) == ("watched", None)


def test_remove_from_list(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 5}, headers=alice)
    assert client.delete("/api/me/library/3", headers=alice).status_code == 204
    assert client.get("/api/me/library", headers=alice).json() == []
    assert client.delete("/api/me/library/3", headers=alice).status_code == 204  # already gone: still fine


def test_library_is_newest_first(client, alice, monkeypatch):
    import app.storage
    times = iter(["2026-10-18T10:00:00+00:00", "2026-10-18T11:00:00+00:00"])
    monkeypatch.setattr(app.storage, "_now", lambda: next(times))
    client.put("/api/me/library/1/status", json={"status": "watching"}, headers=alice)
    client.put("/api/me/library/2/status", json={"status": "watching"}, headers=alice)
    assert ids(client.get("/api/me/library", headers=alice)) == [2, 1]


def test_users_only_see_their_own_library(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 5}, headers=alice)
    token = client.post("/api/auth/local/signup", json={"email": "bob@example.com", "password": "correct horse"}).json()["token"]
    assert client.get("/api/me/library", headers={"Authorization": f"Bearer {token}"}).json() == []


def test_recommendations_use_ratings(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 5}, headers=alice)
    recs = client.get("/api/me/recommendations", headers=alice).json()
    assert recs[0]["id"] == 4 and recs[0]["because"] == "Alien"


def test_recommendations_skip_listed_movies(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 5}, headers=alice)
    client.put("/api/me/library/4/status", json={"status": "plan_to_watch"}, headers=alice)
    assert 4 not in ids(client.get("/api/me/recommendations", headers=alice))


def test_new_user_gets_popular_movies(client, alice):
    assert ids(client.get("/api/me/recommendations", params={"limit": 3}, headers=alice)) == [5, 1, 3]


def test_stats(client, alice):
    client.put("/api/me/library/3/rating", json={"rating": 4}, headers=alice)
    client.put("/api/me/library/2/status", json={"status": "plan_to_watch"}, headers=alice)
    body = client.get("/api/me/stats", headers=alice).json()
    assert body["counts"]["watched"] == 1 and body["counts"]["plan_to_watch"] == 1
    assert body["minutesWatched"] == 117 and body["averageRating"] == 4.0


# --- failures and wiring -----------------------------------------------------

class DownStore:
    def _down(self, *args):
        raise StoreUnavailable("library store unavailable: connection refused")

    get_library = get_ratings = set_rating = clear_rating = set_status = remove = _down


def test_store_down_returns_503_with_message(tiny_model, auth):
    client = TestClient(create_app(Recommender(tiny_model), DownStore(), auth))
    token = auth.sign_up("alice@example.com", "correct horse")["token"]
    headers = {"Authorization": f"Bearer {token}"}
    for response in (
        client.get("/api/me/recommendations", headers=headers),
        client.put("/api/me/library/3/rating", json={"rating": 5}, headers=headers),
        client.delete("/api/me/library/3", headers=headers),
    ):
        assert response.status_code == 503
        assert "library store unavailable" in response.json()["detail"]


def test_cors_allows_browser_on_other_origin(client):
    response = client.get("/api/movies/popular", headers={"Origin": "http://example-bucket.s3-website.amazonaws.com"})
    assert response.headers["access-control-allow-origin"] == "*"


def test_serves_frontend_when_given(tiny_model, store, auth, tmp_path):
    (tmp_path / "index.html").write_text("<h1>Movies</h1>")
    client = TestClient(create_app(Recommender(tiny_model), store, auth, frontend_dir=tmp_path))
    assert client.get("/").text == "<h1>Movies</h1>"
    assert client.get("/api/movies/popular").status_code == 200


def api_gateway_event(method, path, query="", body=None, claims=None):
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": query,
        "headers": {"host": "abc.execute-api.us-east-1.amazonaws.com", "content-type": "application/json"},
        "requestContext": {
            "http": {"method": method, "path": path, "sourceIp": "1.2.3.4", "protocol": "HTTP/1.1"},
            "stage": "$default",
        },
        "isBase64Encoded": False,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    if claims is not None:
        event["requestContext"]["authorizer"] = {"jwt": {"claims": claims, "scopes": None}}
    return event


@pytest.fixture
def lambda_handler(tiny_model, store):
    return Mangum(create_app(Recommender(tiny_model), store, CognitoAuth()), lifespan="off")


def test_lambda_handler_serves_public_api_gateway_event(lambda_handler):
    response = lambda_handler(api_gateway_event("GET", "/api/movies/popular", "limit=1"), None)
    assert response["statusCode"] == 200
    assert [m["id"] for m in json.loads(response["body"])] == [5]


def test_lambda_uses_cognito_user_from_authorizer_claims(lambda_handler, store):
    claims = {"sub": "cognito-sub-1", "email": "a@b.co"}
    put = lambda_handler(api_gateway_event("PUT", "/api/me/library/3/rating", body={"rating": 5}, claims=claims), None)
    assert put["statusCode"] == 200
    assert store.get_ratings("cognito-sub-1") == {3: 5.0}
    library = lambda_handler(api_gateway_event("GET", "/api/me/library", claims=claims), None)
    assert [m["id"] for m in json.loads(library["body"])] == [3]


def test_lambda_without_authorizer_claims_is_401(lambda_handler):
    assert lambda_handler(api_gateway_event("GET", "/api/me/library"), None)["statusCode"] == 401


def test_local_sign_in_endpoints_do_not_exist_with_cognito(lambda_handler):
    event = api_gateway_event("POST", "/api/auth/local/signup", body={"email": "a@b.co", "password": "longenough"})
    assert lambda_handler(event, None)["statusCode"] in (404, 405)
