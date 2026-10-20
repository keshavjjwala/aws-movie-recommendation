#!/usr/bin/env bash
# Runs the whole app locally: DynamoDB Local in Docker + the API/website with uvicorn.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f model/model.json.gz ] || { echo "No model yet -- building it (downloads MovieLens, ~1 min)"; python train.py; }

docker compose up -d dynamodb

export DYNAMODB_ENDPOINT=http://localhost:8001
export LIBRARY_TABLE=Library
export AUTH_MODE=local  # simple built-in accounts instead of Cognito
# DynamoDB Local accepts any credentials; set dummies if none are configured.
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

echo "Open http://localhost:8000 (accounts are local: any email works, nothing is sent)"
exec uvicorn app.server:app --port 8000 "$@"
