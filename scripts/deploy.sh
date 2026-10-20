#!/usr/bin/env bash
# Deploys everything to AWS. Needs: AWS CLI (configured with `aws configure`) and AWS SAM CLI.
set -euo pipefail
cd "$(dirname "$0")/.."
STACK="${STACK_NAME:-movie-recommender}"

[ -f model/model.json.gz ] || python train.py

echo "== Staging Lambda source (app/ + requirements.txt only)"
rm -rf build/lambda-src && mkdir -p build/lambda-src
cp -r app requirements.txt build/lambda-src/
find build/lambda-src -name __pycache__ -prune -exec rm -rf {} +

echo "== Building and deploying stack $STACK"
# The Lambda runs Python 3.12; without it locally, build inside SAM's Docker image instead.
if command -v python3.12 >/dev/null; then sam build; else sam build --use-container; fi
sam deploy --stack-name "$STACK" --resolve-s3 --capabilities CAPABILITY_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
API_URL="$(output ApiUrl)"

echo "== Uploading model to S3"
aws s3 cp model/model.json.gz "s3://$(output ModelBucketName)/model.json.gz"

echo "== Publishing website to S3"
rm -rf build/site && cp -r frontend build/site
POOL_ID="$(output UserPoolId)"
cat > build/site/config.js <<CONFIG
window.API_BASE = "$API_URL";
window.AUTH = { mode: "cognito", region: "${POOL_ID%%_*}", clientId: "$(output UserPoolClientId)" };
CONFIG
aws s3 sync build/site "s3://$(output FrontendBucketName)" --delete

echo
echo "API:     $API_URL"
echo "Website: $(output WebsiteUrl)"
