"""Who is making a request.

CognitoAuth (on AWS): API Gateway's JWT authorizer has already verified the
Cognito token before the Lambda runs, so we only read the verified claims it
puts in the event. Requests on routes without the authorizer carry no claims.

LocalAuth (local development): a small stand-in for Cognito. Accounts live in a
DynamoDB Local table with scrypt-hashed passwords; tokens are HMAC-signed.
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from botocore.exceptions import BotoCoreError, ClientError

from app.storage import _unavailable, dynamodb_resource, ensure_table

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
TOKEN_LIFETIME = 7 * 24 * 3600
SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class CognitoAuth:
    def user(self, request):
        event = request.scope.get("aws.event") or {}
        claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims") or {}
        if not claims.get("sub"):
            return None
        return {"id": claims["sub"], "email": claims.get("email")}


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, **SCRYPT).hex()


class LocalAuth:
    def __init__(self, table_name, secret, endpoint_url=None, region=None, now=time.time):
        self._dynamodb = dynamodb_resource(endpoint_url, region)
        self._table = self._dynamodb.Table(table_name)
        self._secret = secret.encode()
        self._now = now

    def ensure_table(self):
        self._table = ensure_table(self._dynamodb, self._table, [("email", "S")])

    def sign_up(self, email, password):
        email = email.strip().lower()
        if not EMAIL.match(email) or len(email) > 254:
            raise AuthError(422, "Enter a valid email address.")
        if len(password) < MIN_PASSWORD:
            raise AuthError(422, f"Use at least {MIN_PASSWORD} characters for your password.")
        salt = secrets.token_bytes(16)
        user = {"email": email, "userId": secrets.token_hex(16), "salt": salt.hex(), "hash": _hash(password, salt)}
        try:
            self._table.put_item(Item=user, ConditionExpression="attribute_not_exists(email)")
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise AuthError(409, "An account with this email already exists. Sign in instead.") from error
            _unavailable(error)
        except BotoCoreError as error:
            _unavailable(error)
        return self._session(user)

    def sign_in(self, email, password):
        email = email.strip().lower()
        try:
            user = self._table.get_item(Key={"email": email}).get("Item")
        except (BotoCoreError, ClientError) as error:
            _unavailable(error)
        if not user or not hmac.compare_digest(user["hash"], _hash(password, bytes.fromhex(user["salt"]))):
            raise AuthError(401, "Wrong email or password.")
        return self._session(user)

    def user(self, request):
        header = request.headers.get("authorization") or ""
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or "." not in token:
            return None
        payload, _, signature = token.partition(".")
        try:
            if not hmac.compare_digest(_unb64(signature), self._sign(payload)):
                return None
            claims = json.loads(_unb64(payload))
        except ValueError:
            return None
        if claims.get("exp", 0) < self._now():
            return None
        return {"id": claims["sub"], "email": claims["email"]}

    def _sign(self, payload):
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).digest()

    def _session(self, user):
        claims = {"sub": user["userId"], "email": user["email"], "exp": int(self._now() + TOKEN_LIFETIME)}
        payload = _b64(json.dumps(claims).encode())
        return {"token": f"{payload}.{_b64(self._sign(payload))}", "email": user["email"]}
