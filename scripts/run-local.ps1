# Runs the entire Movie Picks app locally on Windows PowerShell:
# 1. Checks/builds the recommendation model if missing
# 2. Starts DynamoDB Local in Docker (if Docker is running)
# 3. Sets local environment variables for DynamoDB Local
# 4. Launches the FastAPI app and static frontend via uvicorn on http://localhost:8000

param(
    [int]$Port = 8000,
    [switch]$NoDocker
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

# Use virtual environment python if present
$PythonCmd = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$UvicornCmd = if (Test-Path ".\.venv\Scripts\uvicorn.exe") { ".\.venv\Scripts\uvicorn.exe" } else { "uvicorn" }

if (-not (Test-Path "model/model.json.gz")) {
    Write-Host "No model yet -- building it (downloads MovieLens dataset, ~1 min)..." -ForegroundColor Cyan
    & $PythonCmd train.py
}

# Check if Docker is available and running for DynamoDB Local
if (-not $NoDocker) {
    $dockerRunning = $false
    try {
        $dockerCheck = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dockerRunning = $true
        }
    } catch {
        $dockerRunning = $false
    }

    if ($dockerRunning) {
        Write-Host "Starting DynamoDB Local container via Docker Compose..." -ForegroundColor Green
        docker compose up -d dynamodb
    } else {
        Write-Host "Notice: Docker Desktop is not running." -ForegroundColor Yellow
        Write-Host "Movie browsing, search, and details will work. Start Docker Desktop and run 'docker compose up -d dynamodb' to enable saving ratings." -ForegroundColor Yellow
    }
}

# Configure environment variables for local DynamoDB
$env:DYNAMODB_ENDPOINT = "http://localhost:8001"
$env:RATINGS_TABLE = "Ratings"
if (-not $env:AWS_ACCESS_KEY_ID) { $env:AWS_ACCESS_KEY_ID = "local" }
if (-not $env:AWS_SECRET_ACCESS_KEY) { $env:AWS_SECRET_ACCESS_KEY = "local" }
if (-not $env:AWS_REGION) { $env:AWS_REGION = "us-east-1" }

Write-Host "`nMovie Picks is running locally!" -ForegroundColor Green
Write-Host "Web Application: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "API Documentation: http://localhost:$Port/docs" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server.`n"

& $UvicornCmd app.server:app --port $Port $args
