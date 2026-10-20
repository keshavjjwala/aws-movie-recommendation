#!/usr/bin/env bash
# Deletes everything deploy.sh created, so nothing keeps costing money.
set -euo pipefail
STACK="${STACK_NAME:-movie-recommender}"

output() {
  aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
# CloudFormation can't delete non-empty buckets, so empty them first.
aws s3 rm "s3://$(output ModelBucketName)" --recursive
aws s3 rm "s3://$(output FrontendBucketName)" --recursive
sam delete --stack-name "$STACK" --no-prompts
