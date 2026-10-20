# Movie Recommendation System on AWS — Design

**Date:** 2026-10-15
**Status:** Approved (design), pending spec review

## Purpose

College project: build a movie recommendation system that uses AWS for its
infrastructure. It must be demoable and explainable, not production-grade.
Primary mode is **running locally**, but the code and infrastructure-as-code
must be ready to deploy to a real AWS account on the free tier.

### Success criteria

- A user can open a web page, enter a name, search movies, rate them, and get
  personalised recommendations plus "similar movies" for any title.
- Runs locally with one Docker command plus one Python command.
- `sam deploy` (with an AWS account) would stand up the same system on AWS:
  S3, Lambda, API Gateway, DynamoDB, IAM.
- Recommender and API logic covered by automated tests.

### Non-goals (YAGNI)

- Authentication/accounts (user = free-text name).
- Movie posters / external APIs (TMDB needs a key).
- Online model retraining; the model is trained offline by a script.
- CloudFront, custom domains, CI/CD.

## Architecture

```
            ┌──────────────────────┐
 Browser ──►│ S3 static website    │  index.html / app.js / style.css
            └──────────┬───────────┘
                       │ fetch (CORS)
            ┌──────────▼───────────┐
            │ API Gateway (HTTP)   │
            └──────────┬───────────┘
            ┌──────────▼───────────┐       ┌──────────────────────┐
            │ Lambda (Python 3.12) │──────►│ S3 model bucket      │
            │ FastAPI + Mangum     │ load  │ model.json.gz        │
            └──────────┬───────────┘ on    └──────────▲───────────┘
                       │        cold start            │ upload
            ┌──────────▼───────────┐       ┌──────────┴───────────┐
            │ DynamoDB "Ratings"   │       │ train.py (offline)   │
            │ PK userId, SK movieId│       │ MovieLens small      │
            └──────────────────────┘       └──────────────────────┘
```

Locally: `uvicorn` serves the same FastAPI app (and the static frontend),
reads the model from a local file, and talks to **DynamoDB Local**
(`amazon/dynamodb-local` Docker image) via `docker compose`.

## Components

### 1. `train.py` — offline model builder

- Downloads MovieLens `ml-latest-small` (if absent) into `data/`.
- Builds a hybrid item–item similarity:
  - **Content:** TF-IDF over `genres` (pipe-split) + user `tags` per movie,
    cosine similarity.
  - **Collaborative:** item × user rating matrix (sparse, mean-centred per
    user), cosine similarity; only movies with ≥ 10 ratings participate.
  - **Hybrid score** = `0.5 * content + 0.5 * collaborative`, with
    collaborative = 0 when either movie has < 10 ratings (so well-known films
    prefer neighbours sharing a real audience over obscure tag look-alikes).
- Keeps only the **top 30 neighbours per movie** → small artifact.
- Also stores movie metadata (id, title, year, genres) and a **popular list**
  (Bayesian-weighted average rating, top 50) for cold start.
- Output: `model/model.json.gz` (plain JSON, gzipped — no pickle, and the
  runtime needs no numpy/pandas/scikit-learn, keeping the Lambda package far
  under the 250 MB limit). Optional `--upload s3://bucket/key`.
- Training deps live in `requirements-train.txt` (pandas, scikit-learn);
  runtime deps in `requirements.txt` (fastapi, mangum, boto3).

### 2. `app/recommender.py` — pure recommendation logic

No AWS or HTTP code; fully unit-testable.

- `Model` dataclass: `movies: dict[int, Movie]`, `neighbours: dict[int, list[tuple[int, float]]]`, `popular: list[int]`.
- `search(q, limit)` — case-insensitive substring match on title, ranked by
  popularity.
- `similar(movie_id, limit)` — top neighbours.
- `recommend(ratings: dict[int, float], limit)` —
  for each rated movie, weight = `rating - 3.0` (so ≤3★ contributes nothing or
  pushes away); score each neighbour by `Σ weight × similarity`; exclude
  already-rated movies; return top N with a "because you liked X" reason
  (the rated movie contributing most). If no positive signal → popular list.

### 3. `app/storage.py` — ratings repository

- `RatingsStore` wrapping a boto3 DynamoDB Table:
  `put_rating(user_id, movie_id, rating)`, `get_ratings(user_id) -> dict`.
- Endpoint URL from env `DYNAMODB_ENDPOINT` (set locally to
  `http://localhost:8001`; unset on AWS). Table name from `RATINGS_TABLE`.
- `ensure_table()` creates the table locally if missing (not used on AWS —
  SAM creates it).

### 4. `app/model_loader.py`

- Loads `model.json.gz` from `MODEL_PATH` (local) or `MODEL_S3_BUCKET` +
  `MODEL_S3_KEY` (AWS, downloaded to `/tmp`). Cached for the process lifetime
  (= Lambda container lifetime).

### 5. `app/main.py` — FastAPI app + Lambda handler

| Method | Path | Description |
|---|---|---|
| GET | `/api/movies/search?q=&limit=` | title search |
| GET | `/api/movies/popular?limit=` | cold-start list |
| GET | `/api/movies/{id}/similar?limit=` | similar movies; 404 if unknown |
| GET | `/api/users/{user}/ratings` | user's ratings with titles |
| PUT | `/api/users/{user}/ratings/{movie_id}` | body `{"rating": 0.5–5}`; 404 unknown movie, 422 bad rating |
| GET | `/api/users/{user}/recommendations?limit=` | personalised list |

- `handler = Mangum(app)` for Lambda.
- CORS enabled (frontend on a different S3 origin).
- Locally, also mounts `frontend/` at `/` so one server serves everything.
- User ids: 1–40 chars, `[A-Za-z0-9_-]`; otherwise 422.

### 6. `frontend/` — static page (no build step)

`index.html`, `app.js`, `style.css`, `config.js` (`API_BASE`, empty locally,
set to API Gateway URL on deploy).
Flow: enter name → search box with results → click stars to rate →
"Recommended for you" (with reasons) and "Your ratings" panels refresh →
clicking a movie shows "Similar movies".

### 7. Infrastructure

- `docker-compose.yml`: DynamoDB Local on host port 8001 (uvicorn uses 8000).
- `template.yaml` (AWS SAM): `RatingsTable` (on-demand billing),
  `ModelBucket`, `FrontendBucket` (static website, public read policy),
  `ApiFunction` (Python 3.12, 512 MB, 15 s timeout, HTTP API event
  `/{proxy+}`, env vars, policies `DynamoDBCrudPolicy` + `S3ReadPolicy`),
  outputs: API URL, website URL, bucket names.
- `scripts/deploy.sh`: `sam build && sam deploy`, upload model, write
  `config.js` with API URL, sync frontend to bucket.
- `docs/architecture.md`: diagram + explanation of each AWS service, for
  slides/viva.

## Error handling

- Unknown movie → 404; invalid rating/user id → 422 (FastAPI validation).
- Model missing at startup → clear error message telling the user to run
  `train.py`.
- DynamoDB unreachable → 503 with message "ratings store unavailable"
  (locally usually means `docker compose up` wasn't run).
- Frontend shows API errors inline instead of failing silently.

## Testing

- `tests/test_recommender.py` — on a tiny hand-built `Model`: similar,
  recommend excludes rated, weighting, cold-start fallback, search.
- `tests/test_storage.py` — `moto` mocked DynamoDB: put/get/overwrite.
- `tests/test_api.py` — FastAPI `TestClient` with tiny model + moto: all
  endpoints, 404/422 paths.
- `tests/test_train.py` — builds model from a tiny synthetic MovieLens-shaped
  CSV set; checks neighbours/popular shape.

## Project layout

```
app/  __init__.py main.py recommender.py storage.py model_loader.py
frontend/  index.html app.js style.css config.js
scripts/  deploy.sh
tests/
train.py  template.yaml  docker-compose.yml  requirements.txt
requirements-train.txt  requirements-dev.txt  README.md  docs/architecture.md  .gitignore
```

`data/` and `model/` are gitignored (dataset and generated artifact).
