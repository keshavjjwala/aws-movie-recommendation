# Deploys the Movie Recommender to AWS using AWS SAM and AWS CLI on Windows PowerShell
param(
    [string]$StackName = "movie-recommender",
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# 1. Verify model exists
if (-not (Test-Path "model/model.json.gz")) {
    Write-Host "Model not found. Building model..." -ForegroundColor Cyan
    python train.py
}

# 2. Stage Lambda source (only app/ and requirements.txt)
Write-Host "== Staging Lambda source (app/ + requirements.txt only)..." -ForegroundColor Cyan
if (Test-Path "build/lambda-src") {
    Remove-Item -Recurse -Force "build/lambda-src"
}
New-Item -ItemType Directory -Path "build/lambda-src" -Force | Out-Null
Copy-Item -Recurse "app" "build/lambda-src/app"
Copy-Item "requirements.txt" "build/lambda-src/"

# Clean any __pycache__ in staged source
Get-ChildItem -Path "build/lambda-src" -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force

# 3. Build with SAM
Write-Host "== Building SAM application..." -ForegroundColor Cyan
sam build

# 4. Deploy with SAM
Write-Host "== Deploying CloudFormation stack: $StackName to region: $Region..." -ForegroundColor Cyan
sam deploy `
  --stack-name "$StackName" `
  --region "$Region" `
  --resolve-s3 `
  --capabilities CAPABILITY_IAM `
  --no-confirm-changeset `
  --no-fail-on-empty-changeset

# 5. Retrieve Stack Outputs
Write-Host "== Fetching stack outputs..." -ForegroundColor Cyan
$ApiUrl = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
$WebsiteUrl = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='WebsiteUrl'].OutputValue" --output text
$ModelBucketName = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='ModelBucketName'].OutputValue" --output text
$FrontendBucketName = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text

# 6. Upload model to S3
Write-Host "== Uploading model to S3 ($ModelBucketName)..." -ForegroundColor Cyan
aws s3 cp model/model.json.gz "s3://$ModelBucketName/model.json.gz" --region "$Region"

# 7. Publish frontend website to S3
Write-Host "== Publishing frontend to S3 ($FrontendBucketName)..." -ForegroundColor Cyan
if (Test-Path "build/site") { Remove-Item -Recurse -Force "build/site" }
Copy-Item -Recurse "frontend" "build/site"
Set-Content -Path "build/site/config.js" -Value "window.API_BASE = `"$ApiUrl`";"
aws s3 sync "build/site" "s3://$FrontendBucketName" --delete --region "$Region"

Write-Host "`nDeployment complete!" -ForegroundColor Green
Write-Host "API Gateway URL: $ApiUrl" -ForegroundColor Cyan
Write-Host "Live Website URL: $WebsiteUrl" -ForegroundColor Green
