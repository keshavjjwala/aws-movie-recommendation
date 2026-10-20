import io
import json
import urllib.error

import pytest

from enrich import FetchError, enrich, load_key, make_fetch, parse_movie

TMDB_ALIEN = {
    "poster_path": "/alien.jpg",
    "backdrop_path": "/alien-wide.jpg",
    "overview": "A crew meets a creature.",
    "tagline": "In space no one can hear you scream.",
    "runtime": 117,
    "credits": {
        "crew": [{"job": "Producer", "name": "Gordon Carroll"}, {"job": "Director", "name": "Ridley Scott"}],
        "cast": [{"name": f"Actor {i}", "order": 6 - i} for i in range(7)],
    },
}


def read_records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_parse_movie_extracts_details():
    record = parse_movie(1, TMDB_ALIEN)
    assert record == {
        "movieId": 1,
        "poster": "/alien.jpg",
        "backdrop": "/alien-wide.jpg",
        "overview": "A crew meets a creature.",
        "tagline": "In space no one can hear you scream.",
        "runtime": 117,
        "director": "Ridley Scott",
        "cast": ["Actor 6", "Actor 5", "Actor 4", "Actor 3", "Actor 2"],  # by billing order
    }


def test_parse_movie_turns_empty_values_into_null():
    record = parse_movie(2, {"poster_path": None, "tagline": "", "runtime": 0, "overview": ""})
    assert record == {
        "movieId": 2, "poster": None, "backdrop": None, "overview": None,
        "tagline": None, "runtime": None, "director": None, "cast": [],
    }


def test_unknown_movie_gives_null_record():
    assert parse_movie(3, None)["poster"] is None and parse_movie(3, None)["cast"] == []


def test_enrich_writes_one_record_per_movie_and_unknown_as_null(tmp_path):
    out = tmp_path / "tmdb.jsonl"
    enrich([(1, 348), (2, 999)], out, fetch=lambda tmdb_id: TMDB_ALIEN if tmdb_id == 348 else None)
    records = {r["movieId"]: r for r in read_records(out)}
    assert records[1]["director"] == "Ridley Scott"
    assert records[2]["poster"] is None


def test_enrich_resumes_without_refetching_or_duplicates(tmp_path):
    out = tmp_path / "tmdb.jsonl"
    enrich([(1, 348)], out, fetch=lambda _: TMDB_ALIEN)
    fetched = []
    enrich([(1, 348), (2, 349)], out, fetch=lambda t: fetched.append(t) or TMDB_ALIEN)
    assert fetched == [349]
    assert sorted(r["movieId"] for r in read_records(out)) == [1, 2]


def test_movie_without_tmdb_id_is_recorded_without_fetching(tmp_path):
    out = tmp_path / "tmdb.jsonl"
    enrich([(1, None)], out, fetch=lambda _: pytest.fail("should not fetch"))
    assert read_records(out)[0]["poster"] is None


def test_failed_movie_is_not_recorded_so_a_rerun_retries_it(tmp_path):
    out = tmp_path / "tmdb.jsonl"

    def flaky(tmdb_id):
        raise FetchError("timeout")

    stats = enrich([(1, 348)], out, fetch=flaky)
    assert stats["failed"] == 1
    assert not out.exists() or read_records(out) == []


class FakeOpener:
    """Stands in for urllib.request.urlopen: replays queued responses/errors."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(json.dumps(outcome).encode())


def http_error(code, headers=None):
    return urllib.error.HTTPError("https://api.themoviedb.org", code, "error", headers or {}, None)


def test_fetch_uses_bearer_header_for_read_access_token():
    opener = FakeOpener(TMDB_ALIEN)
    make_fetch("eyJhbGciOi.token", opener=opener)(348)
    request = opener.requests[0]
    assert request.get_header("Authorization") == "Bearer eyJhbGciOi.token"
    assert "api_key" not in request.full_url
    assert "/movie/348?" in request.full_url and "append_to_response=credits" in request.full_url


def test_fetch_uses_query_param_for_v3_api_key():
    opener = FakeOpener(TMDB_ALIEN)
    make_fetch("abc123", opener=opener)(348)
    assert "api_key=abc123" in opener.requests[0].full_url
    assert opener.requests[0].get_header("Authorization") is None


def test_fetch_returns_none_for_unknown_movie():
    assert make_fetch("abc", opener=FakeOpener(http_error(404)))(1) is None


def test_fetch_waits_and_retries_when_rate_limited():
    waits = []
    opener = FakeOpener(http_error(429, {"Retry-After": "3"}), http_error(429), TMDB_ALIEN)
    data = make_fetch("abc", opener=opener, sleep=waits.append)(348)
    assert data == TMDB_ALIEN
    assert waits == [3.0, 2.0]


def test_fetch_gives_up_after_three_errors():
    opener = FakeOpener(http_error(500), urllib.error.URLError("down"), http_error(502))
    with pytest.raises(FetchError):
        make_fetch("abc", opener=opener, sleep=lambda s: None)(348)


def test_load_key_prefers_environment_then_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nTMDB_API_KEY="from-file"\n')
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    assert load_key(env_file) == "from-file"
    monkeypatch.setenv("TMDB_API_KEY", "from-env")
    assert load_key(env_file) == "from-env"
    monkeypatch.delenv("TMDB_API_KEY")
    assert load_key(tmp_path / "missing.env") is None


def test_rejected_key_stops_with_a_clear_message():
    with pytest.raises(SystemExit, match="TMDB rejected the key"):
        make_fetch("wrong", opener=FakeOpener(http_error(401)))(862)


def test_check_key_makes_a_single_request_before_the_run():
    from enrich import check_key

    opener = FakeOpener(http_error(401))
    with pytest.raises(SystemExit):
        check_key(make_fetch("wrong", opener=opener))
    assert len(opener.requests) == 1
