# Deletes everything deployed on AWS so no ongoing charges occur
param(
    [string]$StackName = "movie-recommender",
    [string]$Region = "us-east-1"
)

$ErrorActionPreference = "Stop"

Write-Host "== Emptying S3 buckets before CloudFormation stack deletion..." -ForegroundColor Cyan
try {
    $ModelBucketName = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='ModelBucketName'].OutputValue" --output text 2>$null
    if ($ModelBucketName -and $ModelBucketName -ne "None") {
        Write-Host "Emptying model bucket: $ModelBucketName"
        aws s3 rm "s3://$ModelBucketName" --recursive --region "$Region"
    }

    $FrontendBucketName = aws cloudformation describe-stacks --stack-name "$StackName" --region "$Region" --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text 2>$null
    if ($FrontendBucketName -and $FrontendBucketName -ne "None") {
        Write-Host "Emptying frontend bucket: $FrontendBucketName"
        aws s3 rm "s3://$FrontendBucketName" --recursive --region "$Region"
    }
} catch {
    Write-Host "Notice: Could not query bucket names directly. Proceeding with stack deletion..." -ForegroundColor Yellow
}

Write-Host "== Deleting SAM / CloudFormation stack: $StackName in region: $Region..." -ForegroundColor Cyan
sam delete --stack-name "$StackName" --region "$Region" --no-prompts

Write-Host "`nTeardown complete. All AWS resources have been removed from your account." -ForegroundColor Green
