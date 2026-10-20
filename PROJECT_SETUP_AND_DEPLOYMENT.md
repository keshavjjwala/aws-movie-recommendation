# Movie Picks: Complete Project Setup and Running Guide

This guide provides end-to-end instructions for setting up, configuring, running, and verifying the **Movie Picks** movie recommendation system on a local machine, with **Windows PowerShell** as the primary operating system environment (and Unix/macOS Bash reference commands included).

---

## 1. Project Overview & Features Actually Implemented

**Movie Picks** is a full-stack, serverless-ready movie recommendation web application. It combines collaborative filtering with content-based metadata to provide personalized movie recommendations in a sleek, dark-themed streaming UI without requiring user account creation or passwords.

### Implemented Features

- **Personalized Recommendations**:
  - Item-item hybrid recommendation algorithm combining **content-based TF-IDF similarity** (genres and tags) with **collaborative filtering** (mean-centered user ratings cosine similarity).
  - Dynamic user score computation with explanation attribution ("Because you liked *Movie X*").
  - Intelligent cold-start fallback to Bayesian average popular movies when no ratings or positive signals exist.
- **Movie Catalog & Search**:
  - Live search across 9,700+ movies with instant debounce and title relevance ranking weighted by rating volume.
  - Movie details modal/page presenting high-resolution posters, backdrops, plot summaries, director, top-5 cast members, runtime, release year, and genres.
  - "More Like This" similar titles carousel computed from precalculated nearest-neighbor matrix.
- **Anonymous Session & Ratings Management**:
  - Zero-friction onboarding: browser automatically generates a persistent anonymous UUID stored in `localStorage`.
  - Star rating system (0.5 to 5.0 stars) with real-time feedback and dynamic counter badge.
  - "My Ratings" management page with rating modification, deletion, and "Start Over" session reset.
- **Dual Runtime Architecture**:
  - **Local Development**: Runs with FastAPI and Uvicorn serving both the API and the static frontend from a single port, backed by DynamoDB Local.
  - **Cloud/AWS Ready**: SAM template configures API Gateway, Lambda (via Mangum ASGI adapter), DynamoDB, S3 static website hosting, and S3 model artifact storage.

---

## 2. Technology Stack & Dependency Versions

### Backend & Machine Learning Stack

| Component | Technology | Version Used / Tested | Purpose |
|---|---|---|---|
| **Language** | Python | 3.12+ (tested on 3.13.15) | Core application runtime and data pipelines |
| **Web Framework** | FastAPI | `0.115.6` | High-performance asynchronous HTTP REST API |
| **ASGI Server** | Uvicorn | `0.34.0` | Local development HTTP server |
| **AWS Lambda Adapter** | Mangum | `0.19.0` | Serverless ASGI adapter for AWS Lambda |
| **AWS SDK** | Boto3 & Botocore | `1.35.90` / `1.35.99` | Client for Amazon DynamoDB and Amazon S3 |
| **Data Processing** | Pandas | `2.2.3` | Processing MovieLens tabular ratings and metadata |
| **Machine Learning** | Scikit-Learn | `1.6.0` | TF-IDF vectorization and matrix normalization |
| **Sparse Math** | SciPy | `1.14.1` | Compressed Sparse Row (CSR) matrix dot products |
| **SSL Certificates** | Certifi | `>=2024.7.4` | Mozilla CA certificate bundle for secure HTTPS |
| **Testing** | Pytest | `8.3.4` | Automated test suite execution |
| **AWS Mocking** | Moto | `5.0.24` | In-memory mocking of DynamoDB and S3 in tests |
| **HTTP Client (Dev)** | HTTPX | `0.28.1` | ASGI test client engine |

### Frontend Stack

| Component | Technology | Purpose |
|---|---|---|
| **Markup** | HTML5 (Semantic) | Single-page application shell (`frontend/index.html`) |
| **Styles** | Vanilla CSS3 | Dark-mode design system with CSS custom properties, grid layouts, and responsive flexboxes (`frontend/style.css`) |
| **Logic** | Vanilla JavaScript (ES Modules) | Client-side routing, API communication, state management, and UI rendering (`frontend/js/`) |
| **Build Step** | **None (Zero Build)** | Direct ES module loading via `<script type="module">`. No Node.js, Webpack, or Vite required. |
| **Typography** | Google Fonts | Instrument Sans and Big Shoulders Display |
| **External CDN** | TMDB Image CDN (`image.tmdb.org`) | Posters (`w342`) and backdrops (`w1280`) |

---

## 3. Repository Structure & File Purpose

```
aws-movie-recommendation/
├── .env.example                 # Template for local environment variables (TMDB API key)
├── .gitignore                   # Ignores .env, .venv, data/, model/, and build artifacts
├── pyproject.toml               # Pytest configuration and warning filters
├── requirements.txt             # Minimal production runtime dependencies (FastAPI, Mangum, Boto3)
├── requirements-train.txt       # Dependencies for model training and dataset download
├── requirements-dev.txt         # Development & test dependencies (includes all requirements + pytest, moto, uvicorn)
├── enrich.py                    # Offline pipeline: fetches posters, cast, crew from TMDB API
├── train.py                     # Offline pipeline: downloads MovieLens, builds hybrid recommendation model
├── template.yaml                # AWS SAM / CloudFormation serverless infrastructure definition
├── docker-compose.yml           # Amazon DynamoDB Local service definition
│
├── app/                         # Core Python application package
│   ├── __init__.py
│   ├── main.py                  # FastAPI route definitions, CORS middleware, and static mount
│   ├── server.py                # Environment configuration wiring, DynamoDB init, Lambda entry point
│   ├── recommender.py           # Pure-Python recommendation algorithms and search index
│   ├── storage.py               # DynamoDB ratings store client and table creation logic
│   └── model_loader.py          # Loads gzipped JSON model from local disk or S3 bucket
│
├── frontend/                    # Static single-page application (served by FastAPI or S3)
│   ├── index.html               # Main HTML entry point
│   ├── style.css                # Complete CSS design system
│   ├── config.js                # API origin configuration (overwritten during AWS deployment)
│   └── js/
│       ├── main.js              # Routing coordinator, search debouncer, event listeners
│       ├── router.js            # Hash-based SPA routing (#/, #/movie/:id, #/search, etc.)
│       ├── api.js               # Fetch wrapper for all REST endpoints
│       ├── user.js              # Anonymous user UUID generator and rating state manager
│       ├── ui.js                # Reusable UI component builders (cards, badges, modals, stars)
│       └── views/
│           ├── welcome.js       # First-time visitor onboarding (rate 3 movies)
│           ├── home.js          # Personalized home rows ("Because you liked...")
│           ├── movie.js         # Full movie details view with "More like this" carousel
│           ├── search.js        # Real-time search results grid
│           └── ratings.js       # User ratings library and session reset
│
├── scripts/
│   ├── run-local.ps1            # Windows PowerShell 1-command startup script
│   ├── run-local.sh             # Unix/Linux/macOS Bash 1-command startup script
│   ├── deploy.sh                # AWS SAM build and CloudFormation deployment script
│   └── destroy.sh               # AWS CloudFormation teardown script
│
├── tests/                       # Pytest automated test suite (86 tests)
│   ├── conftest.py              # Shared fixtures and mock dataset definitions
│   ├── test_api.py              # API routes, status codes, CORS, and error cases
│   ├── test_recommender.py      # Recommender scoring, filtering, and edge cases
│   ├── test_storage.py          # DynamoDB store operations and connection failure handling
│   ├── test_model_loader.py     # Local and S3 model loading logic
│   ├── test_enrich.py           # TMDB API fetching, rate-limiting, and resume capability
│   └── test_train.py            # Model training, TF-IDF calculation, and matrix math
│
├── data/                        # [Generated] Raw datasets (ml-latest-small) and tmdb.jsonl
└── model/                       # [Generated] Compressed model artifact (model.json.gz)
```

---

## 4. Prerequisites & Software Requirements

Ensure the following tools are installed on your workstation:

1. **Operating System**: Windows 10/11 (with PowerShell 5.1 or PowerShell 7+), macOS, or Linux.
2. **Python**: Version **3.12** or **3.13** (Verify by running `python --version`).
3. **Git**: For version control.
4. **Docker Desktop** *(Optional for basic movie browsing; Required for saving ratings locally)*:
   - Needed to run Amazon DynamoDB Local (`docker-compose.yml`).
5. **TMDB API Account** *(Optional but recommended)*:
   - Free API key or Read Access Token from [The Movie Database (themoviedb.org)](https://www.themoviedb.org/) for real movie posters, backdrops, cast, and overviews.

---

## 5. Step-by-Step Local Setup Instructions (Windows PowerShell)

Open **Windows PowerShell** as a regular user and execute the steps below from within the repository root directory.

### Step 5.1: Navigate to Project Directory

```powershell
# Expected Directory: repository root
cd "d:\movie recommendation\aws-movie-recommendation"
```

### Step 5.2: Create and Activate Python Virtual Environment

```powershell
# Create virtual environment named .venv
python -m venv .venv

# Activate virtual environment in PowerShell
.\.venv\Scripts\Activate.ps1
```

> **Troubleshooting PowerShell Script Execution**:
> If PowerShell displays `File ... cannot be loaded because running scripts is disabled on this system`, run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

### Step 5.3: Upgrade Pip and Install Dependencies

```powershell
# Upgrade pip inside virtual environment
python -m pip install --upgrade pip

# Install development and training dependencies
pip install -r requirements-dev.txt
```

*Expected Result*: All required packages (`fastapi`, `uvicorn`, `pandas`, `scikit-learn`, `scipy`, `boto3`, `moto`, `pytest`, `certifi`) are installed successfully into `.venv`.

### Step 5.4: Frontend Setup

The frontend is written in vanilla HTML, CSS, and ES Modules. **There is no separate npm install or build command needed.** When the backend starts, FastAPI serves the `frontend/` directory directly at `http://localhost:8000/`.

---

## 6. Environment Variables & TMDB Configuration

### Step 6.1: Create Local `.env` File

Copy the provided `.env.example` template to `.env`:

```powershell
Copy-Item .env.example .env
```

### Step 6.2: Obtain a Free TMDB API Key

1. Create a free account at [themoviedb.org/signup](https://www.themoviedb.org/signup).
2. Go to **Settings** → **API** (`https://www.themoviedb.org/settings/api`).
3. Request an API key (choose "Developer").
4. Copy either:
   - The **API Key (v3 auth)** (a 32-character hex string), OR
   - The **API Read Access Token (v4 auth)** (a long JWT starting with `eyJ...`).

### Step 6.3: Configure `.env`

Open `.env` in any text editor (e.g., `notepad .env`) and set your key:

```env
# Either v3 API Key or v4 Read Access Token
TMDB_API_KEY=your_actual_tmdb_api_key_here
```

> **Security Note**:
> - The `.env` file is excluded from Git via `.gitignore`. Never commit `.env` to source control.
> - The `TMDB_API_KEY` is **only** used locally by `enrich.py` to download movie metadata. It is never embedded in the model, sent to the browser, or uploaded to AWS.

### Step 6.4: Environment Variables Reference

| Variable Name | Default Value | Purpose |
|---|---|---|
| `TMDB_API_KEY` | *(None)* | Read by `enrich.py` to authenticate against TMDB API |
| `DYNAMODB_ENDPOINT` | `None` (AWS) / `http://localhost:8001` (Local) | Points Boto3 to local DynamoDB container |
| `RATINGS_TABLE` | `Ratings` | DynamoDB table name storing user ratings |
| `AWS_ACCESS_KEY_ID` | `local` (in local dev scripts) | Dummy key accepted by DynamoDB Local |
| `AWS_SECRET_ACCESS_KEY` | `local` (in local dev scripts) | Dummy secret accepted by DynamoDB Local |
| `AWS_REGION` | `us-east-1` | AWS region configuration for Boto3 |
| `MODEL_PATH` | `model/model.json.gz` | Path to precomputed recommendation model file |
| `MODEL_S3_BUCKET` | *(None)* | If set, `model_loader.py` fetches the model from S3 |

---

## 7. Dataset Download & Model Training

The system uses the GroupLens **MovieLens "ml-latest-small"** dataset (100,000 ratings across 9,700 movies by 600 users).

### Step 7.1: Quick Start (Base Model with Generated Posters)

To start immediately without waiting for TMDB enrichment:

```powershell
python train.py
```

*What this does*:
1. Automatically downloads `ml-latest-small.zip` from GroupLens into `data/`.
2. Computes TF-IDF genre and user-tag content similarities.
3. Computes mean-centered collaborative filtering matrix.
4. Generates hybrid top-30 nearest neighbors for each movie.
5. Saves the compressed model to `model/model.json.gz` (~1 MB).

### Step 7.2: Full Enrichment (Real Posters, Cast, and Plot Summaries)

To enrich all movies with official TMDB images and details:

```powershell
# 1. Fetch details from TMDB (writes data/tmdb.jsonl)
python enrich.py

# 2. Rebuild the model to merge TMDB details
python train.py
```

*Features of `enrich.py`*:
- Multi-threaded: Uses 8 worker threads for concurrent retrieval.
- Resumable: You can interrupt it anytime (`Ctrl+C`); running `python enrich.py` again resumes exactly where it stopped without repeating completed movies.

---

## 8. Starting the Application

You can launch the complete application either with the automated script or manually.

### Option A: Using the Automated PowerShell Script (Recommended)

Run the included PowerShell script:

```powershell
.\scripts\run-local.ps1
```

*What the script does*:
1. Verifies virtual environment and model file availability.
2. Checks if Docker Desktop is running and launches the DynamoDB Local container (`docker compose up -d dynamodb`).
3. Sets local environment variables (`DYNAMODB_ENDPOINT=http://localhost:8001`, `AWS_ACCESS_KEY_ID=local`, etc.).
4. Starts Uvicorn on `http://localhost:8000`.

### Option B: Manual PowerShell Commands

If you prefer to run the steps manually:

```powershell
# 1. (Optional) Start DynamoDB Local if Docker Desktop is running:
docker compose up -d dynamodb

# 2. Set environment variables for the current PowerShell session:
$env:DYNAMODB_ENDPOINT = "http://localhost:8001"
$env:RATINGS_TABLE = "Ratings"
$env:AWS_ACCESS_KEY_ID = "local"
$env:AWS_SECRET_ACCESS_KEY = "local"
$env:AWS_REGION = "us-east-1"

# 3. Start the application with Uvicorn:
uvicorn app.server:app --port 8000
```

### Option C: Unix / Linux / macOS (Bash)

```bash
source .venv/bin/activate
./scripts/run-local.sh
```

---

## 9. Local URLs & Verification

Once running, access the following endpoints in your web browser:

| Resource | URL | Description |
|---|---|---|
| **Web Application** | [http://localhost:8000](http://localhost:8000) | Main streaming-style user interface |
| **Interactive API Docs (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive testing of all REST endpoints |
| **Alternative API Docs (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean API documentation schema |
| **OpenAPI Specification** | [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) | Raw OpenAPI JSON schema |

### Verifying Application Functionality

1. **Home Page & Welcome Onboarding**:
   - Open `http://localhost:8000`. New visitors are presented with the onboarding screen asking to rate 3 movies you love.
2. **Search**:
   - Type `Matrix` or `Toy Story` into the top search bar. Instant debounced results should appear with titles and years.
3. **Movie Details Modal**:
   - Click on any movie card. A modal opens showing backdrop, poster, overview, runtime, genres, director, cast, and "More Like This" similar titles.
4. **Ratings & Personalized Recommendations**:
   - Rate 3 or more movies with 4 or 5 stars.
   - Navigate to the Home page (`#/`) or My Ratings (`#/ratings`).
   - You will see custom recommendation rows such as *"Because you liked The Matrix"*.
5. **Session Reset**:
   - Click "My ratings" in the navigation bar and click "Start over" to generate a new anonymous profile.

---

## 10. Running Automated Tests

The repository includes a comprehensive Pytest test suite covering all layers of the system.

```powershell
# Ensure virtual environment is active
.\.venv\Scripts\Activate.ps1

# Run the complete test suite
pytest -v
```

### Test Coverage Summary (86 Tests)

- `tests/test_api.py` (29 tests):
  - Search query validation, limit parameter boundaries, 404/422 error handling.
  - User rating CRUD operations (PUT, GET, DELETE).
  - CORS cross-origin headers and FastAPI static file mounting.
  - Mangum AWS Lambda handler integration with simulated API Gateway v2 payloads.
  - 503 error handling when the database store is unavailable.
- `tests/test_recommender.py` (19 tests):
  - Pure-Python hybrid recommendation scoring and candidate pruning.
  - "Because you liked" top-contributor explanation attribution.
  - Cold-start fallback to Bayesian average popular movies.
  - Special character search escaping and ranking.
- `tests/test_storage.py` (8 tests):
  - DynamoDB item serialization (converting floats to Decimal).
  - User session isolation and idempotent table initialization (`ensure_table`).
  - Timeout and connection error handling (`StoreUnavailable`).
- `tests/test_enrich.py` (15 tests):
  - TMDB response parsing (directors, top-5 cast, image paths).
  - Bearer token (v4) and query parameter (v3) authentication headers.
  - HTTP 429 rate limit backoff and `Retry-After` header parsing.
  - Incremental resume without refetching existing records.
- `tests/test_train.py` (12 tests):
  - MovieLens dataset parsing and title article cleanup (*"Matrix, The"* → *"The Matrix"*).
  - TF-IDF content matrix calculation and cosine similarity.
  - Mean-centered collaborative filtering matrix and Bayesian popular formula.
- `tests/test_model_loader.py` (3 tests):
  - Loading gzipped JSON from local disk and downloading from simulated S3 buckets.

---

## 11. Common Errors & Troubleshooting

### Issue 1: `SSL: CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate` during `python train.py`
- **Cause**: On Windows, Python's built-in `urllib` may not have access to the system root certificate store when downloading the MovieLens dataset from `grouplens.org`.
- **Solution**: The repository has been patched to use `certifi`'s verified CA bundle in `train.py`. Ensure `certifi` is installed:
  ```powershell
  pip install certifi
  ```

### Issue 2: `503 Service Unavailable: ratings store unavailable: Unable to locate credentials`
- **Cause**: The application was started without setting `DYNAMODB_ENDPOINT` or dummy AWS credentials, causing Boto3 to seek real AWS credentials.
- **Solution**: Always launch local instances using `.\scripts\run-local.ps1`, or set environment variables in your terminal:
  ```powershell
  $env:DYNAMODB_ENDPOINT = "http://localhost:8001"
  $env:AWS_ACCESS_KEY_ID = "local"
  $env:AWS_SECRET_ACCESS_KEY = "local"
  $env:AWS_REGION = "us-east-1"
  ```

### Issue 3: `503 Service Unavailable: Could not connect to the endpoint URL: http://localhost:8001`
- **Cause**: The backend is configured to use DynamoDB Local, but the Docker container is not running.
- **Solution**:
  1. Start Docker Desktop.
  2. Start the DynamoDB container:
     ```powershell
     docker compose up -d dynamodb
     ```
  3. Verify the container is running:
     ```powershell
     docker ps
     ```

### Issue 4: `TMDB rejected the key (401). Check TMDB_API_KEY in .env.`
- **Cause**: The key in `.env` is invalid, expired, or contains quotes/whitespace.
- **Solution**: Open `.env` and verify your key from `themoviedb.org/settings/api`. Ensure there are no spaces or extra quotes:
  ```env
  TMDB_API_KEY=a1b2c3d4e5f6...
  ```

### Issue 5: Port 8000 is already in use
- **Cause**: Another instance of Uvicorn or another application is bound to port 8000.
- **Solution**: Run on a different port:
  ```powershell
  uvicorn app.server:app --port 8080
  ```
  Then access `http://localhost:8080`.

### Issue 6: `Model file model/model.json.gz not found`
- **Cause**: The server was started before compiling the model.
- **Solution**: Build the model:
  ```powershell
  python train.py
  ```

---

## 12. Roadmap Considerations for Future Docker & AWS Deployment

When you are ready to implement Docker containers and deploy to AWS, keep the following considerations in mind:

### Docker Architecture Considerations
- **Multi-Stage API Dockerfile**:
  - Use `python:3.12-slim` as the base image.
  - Install dependencies from `requirements.txt` only (keeps image under 100 MB; avoids large ML training libraries like `scikit-learn` in production).
  - Mount or COPY `model/model.json.gz` into the container image.
- **DynamoDB Local Persistence**:
  - The provided `docker-compose.yml` mounts a named volume `dynamodb-data:/home/dynamodblocal/data`.
  - Use `docker compose down -v` only when you wish to wipe test ratings.

### AWS Deployment Architecture (as configured in `template.yaml`)
- **AWS SAM (CloudFormation)**:
  - `template.yaml` defines the serverless stack: an API Gateway HTTP API, a Python 3.12 Lambda function (`app.server.handler`), an Amazon DynamoDB `Ratings` table (PAY_PER_REQUEST billing), and an S3 bucket for the static website.
- **Static Website Hosting (S3)**:
  - `scripts/deploy.sh` automatically updates `frontend/config.js` with the live API Gateway endpoint (`window.API_BASE = "https://...execute-api...amazonaws.com";`) before syncing files to the S3 bucket.
- **Decoupled Model Storage (S3)**:
  - To retrain without redeploying code, upload `model.json.gz` to an S3 bucket via `python train.py --upload s3://<bucket>/model.json.gz`.
  - The Lambda function downloads and caches the model into `/tmp/model.json.gz` during cold starts.
- **Learner Lab / Restricted IAM Permissions**:
  - If deploying under an AWS Learner Lab or restricted AWS Academy account that prohibits IAM role creation, replace the `Policies:` block in `template.yaml` with your assigned `Role: <LabRole-ARN>`.
