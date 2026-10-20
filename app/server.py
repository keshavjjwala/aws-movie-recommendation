"""Entry point, configured by environment variables.

Locally:   uvicorn app.server:app          (see scripts/run-local.sh)
On Lambda: handler = app.server.handler    (see template.yaml)
"""

import logging
import os
from pathlib import Path

from mangum import Mangum

from app.auth import CognitoAuth, LocalAuth
from app.main import create_app
from app.model_loader import load_model
from app.recommender import Recommender
from app.storage import LibraryStore, StoreUnavailable

log = logging.getLogger(__name__)

on_lambda = "AWS_LAMBDA_FUNCTION_NAME" in os.environ
dynamodb_endpoint = os.environ.get("DYNAMODB_ENDPOINT") or None
store = LibraryStore(os.environ.get("LIBRARY_TABLE", "Library"), endpoint_url=dynamodb_endpoint)

auth_mode = os.environ.get("AUTH_MODE", "cognito" if on_lambda else "local")
if auth_mode == "cognito":
    auth = CognitoAuth()  # tokens are verified by API Gateway's JWT authorizer
elif auth_mode == "local" and not on_lambda:
    auth = LocalAuth(
        os.environ.get("LOCAL_USERS_TABLE", "LocalUsers"),
        secret=os.environ.get("LOCAL_AUTH_SECRET", "local-dev-only"),
        endpoint_url=dynamodb_endpoint,
    )
else:
    raise RuntimeError(f"AUTH_MODE={auth_mode!r} is not allowed here (use 'cognito' on AWS, 'local' on your machine)")

if dynamodb_endpoint:  # local DynamoDB: create the tables on first run
    try:
        store.ensure_table()
        if isinstance(auth, LocalAuth):
            auth.ensure_table()
    except StoreUnavailable as error:
        log.warning("%s -- start it with: docker compose up -d", error)

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app = create_app(
    Recommender(load_model()),
    store,
    auth,
    frontend_dir=frontend_dir if not on_lambda and frontend_dir.exists() else None,
)
handler = Mangum(app, lifespan="off")
