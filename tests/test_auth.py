import pytest
from moto import mock_aws

from app.auth import AuthError, CognitoAuth, LocalAuth


class FakeRequest:
    def __init__(self, headers=None, scope=None):
        self.headers = headers or {}
        self.scope = scope or {}


@pytest.fixture
def clock():
    return {"now": 1_000_000.0}


@pytest.fixture
def auth(monkeypatch, clock):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        auth = LocalAuth("LocalUsers", secret="test-secret", now=lambda: clock["now"])
        auth.ensure_table()
        yield auth


def bearer(token):
    return FakeRequest({"authorization": f"Bearer {token}"})


def test_sign_up_returns_a_token_for_that_user(auth):
    session = auth.sign_up("Alice@Example.com", "correct horse")
    assert session["email"] == "alice@example.com"
    user = auth.user(bearer(session["token"]))
    assert user["email"] == "alice@example.com" and user["id"]


def test_sign_in_with_right_password(auth):
    first = auth.sign_up("alice@example.com", "correct horse")
    again = auth.sign_in("ALICE@example.com ", "correct horse")
    assert auth.user(bearer(again["token"]))["id"] == auth.user(bearer(first["token"]))["id"]


def test_sign_in_with_wrong_password_or_unknown_email_is_401(auth):
    auth.sign_up("alice@example.com", "correct horse")
    for email, password in [("alice@example.com", "wrong horse"), ("nobody@example.com", "correct horse")]:
        with pytest.raises(AuthError) as error:
            auth.sign_in(email, password)
        assert error.value.status == 401
        assert error.value.message == "Wrong email or password."


def test_duplicate_sign_up_is_409(auth):
    auth.sign_up("alice@example.com", "correct horse")
    with pytest.raises(AuthError) as error:
        auth.sign_up("alice@example.com", "another one")
    assert error.value.status == 409


@pytest.mark.parametrize("email,password", [("not-an-email", "longenough"), ("a@b.co", "short")])
def test_invalid_sign_up_is_422(auth, email, password):
    with pytest.raises(AuthError) as error:
        auth.sign_up(email, password)
    assert error.value.status == 422


def test_password_is_not_stored_in_plain_text(auth):
    auth.sign_up("alice@example.com", "correct horse")
    item = auth._table.get_item(Key={"email": "alice@example.com"})["Item"]
    assert "correct horse" not in str(item)


def test_tampered_token_is_rejected(auth):
    token = auth.sign_up("alice@example.com", "correct horse")["token"]
    payload, signature = token.split(".")
    assert auth.user(bearer(payload + "x." + signature)) is None
    assert auth.user(bearer(token[:-2] + "AA")) is None


def test_token_from_another_secret_is_rejected(auth, clock):
    token = auth.sign_up("alice@example.com", "correct horse")["token"]
    other = LocalAuth("LocalUsers", secret="other-secret", now=lambda: clock["now"])
    assert other.user(bearer(token)) is None


def test_expired_token_is_rejected(auth, clock):
    token = auth.sign_up("alice@example.com", "correct horse")["token"]
    clock["now"] += 8 * 24 * 3600
    assert auth.user(bearer(token)) is None


@pytest.mark.parametrize("header", [None, "", "Bearer", "Basic abc", "Bearer not.valid", "Bearer ..."])
def test_missing_or_malformed_header_means_signed_out(auth, header):
    request = FakeRequest({"authorization": header} if header is not None else {})
    assert auth.user(request) is None


def test_cognito_reads_claims_verified_by_api_gateway():
    event = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "abc-123", "email": "a@b.co"}}}}}
    assert CognitoAuth().user(FakeRequest(scope={"aws.event": event})) == {"id": "abc-123", "email": "a@b.co"}


def test_cognito_without_claims_is_signed_out():
    assert CognitoAuth().user(FakeRequest(scope={"aws.event": {"requestContext": {}}})) is None
    assert CognitoAuth().user(FakeRequest(headers={"authorization": "Bearer forged"})) is None
