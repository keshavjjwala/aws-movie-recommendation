# Movie Recommendation System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hybrid (content + collaborative) movie recommender served by a FastAPI app that runs locally against DynamoDB Local and deploys to AWS Lambda/API Gateway/DynamoDB/S3 via SAM.

**Architecture:** Offline `train.py` turns MovieLens small into a gzipped-JSON model of top-30 neighbours per movie. A pure-Python `recommender` module serves search/similar/recommend from that model; `storage` persists ratings in DynamoDB; `main` exposes a FastAPI app (wrapped by Mangum for Lambda) plus a static frontend.

**Tech Stack:** Python 3.12+ (Lambda runtime 3.12), FastAPI, Mangum, boto3, pandas + scikit-learn (training only), pytest + moto + httpx (tests), Docker Compose (DynamoDB Local), AWS SAM.

**Spec:** `docs/superpowers/specs/2026-10-15-movie-recommendation-design.md`

## Global Constraints

- Runtime deps limited to `fastapi`, `mangum`, `boto3` (Lambda package must stay < 250 MB; no numpy/pandas at runtime).
- Model artifact: `model/model.json.gz`, plain JSON (no pickle).
- Top 30 neighbours per movie; popular list = top 50 by Bayesian-weighted average.
- Hybrid score = `0.5 * content + 0.5 * collaborative`; collaborative = 0 unless both movies have ≥ 10 ratings.
- Recommendation weight = `rating - 3.0`.
- Ratings in [0.5, 5.0]; user ids match `^[A-Za-z0-9_-]{1,40}$`.
- DynamoDB Local on host port 8001; uvicorn on 8000.
- Env vars: `RATINGS_TABLE`, `DYNAMODB_ENDPOINT`, `MODEL_PATH`, `MODEL_S3_BUCKET`, `MODEL_S3_KEY`.

## Review Focus

1. Search query with regex/special chars (e.g. `(`, `*`) → plain substring match, no crash. Test in Task 2.
2. User who only rated movies ≤ 3★ → falls back to popular list, not empty. Test in Task 2.
3. Rating a movie not in the model → 404, not stored. Test in Task 4.
4. Re-rating the same movie → overwrites (single row). Test in Task 3.
5. DynamoDB Local not running → 503 with readable message, not a 500 traceback. Test in Task 4.

---

### Task 1: Project scaffolding + training pipeline

**Files:** Create `requirements.txt`, `requirements-train.txt`, `requirements-dev.txt`, `pyproject.toml` (pytest config), `train.py`, `tests/test_train.py`

**Interfaces — Produces:** `train.build_model(movies: DataFrame, ratings: DataFrame, tags: DataFrame, k=30, n_popular=50) -> dict` returning
`{"movies": {str(id): {"title", "year", "genres": [..]}}, "neighbours": {str(id): [[id, score], ...]}, "popular": [id, ...]}`;
`train.save_model(model: dict, path)` writes gzipped JSON.

- [ ] Write tests on a synthetic 6-movie dataset: neighbours ≤ k and exclude self; same-genre movies are neighbours; popular sorted by weighted rating; titles parsed into title/year; output round-trips through save/load.
- [ ] Run tests → fail. Implement. Run → pass. Commit.

### Task 2: Recommender core

**Files:** Create `app/__init__.py`, `app/recommender.py`, `tests/test_recommender.py`

**Interfaces — Consumes:** model dict from Task 1. **Produces:**
`Recommender(model: dict)` with `.movie(id) -> dict | None`, `.search(q, limit=20) -> list[dict]`, `.popular(limit=20) -> list[dict]`, `.similar(id, limit=10) -> list[dict]`, `.recommend(ratings: dict[int, float], limit=20) -> list[dict]`. Each movie dict: `{"id", "title", "year", "genres"}`; similar adds `"score"`; recommend adds `"score"` and `"because"` (title).

- [ ] Tests: search case-insensitive + special chars; similar unknown id → `[]`; recommend excludes rated, uses weight `rating-3`, reason = top contributor; low-only ratings → popular fallback (excluding rated).
- [ ] Fail → implement → pass → commit.

### Task 3: Ratings storage

**Files:** Create `app/storage.py`, `tests/test_storage.py`

**Interfaces — Produces:** `RatingsStore(table_name, endpoint_url=None, region="us-east-1")`, `.ensure_table()`, `.put_rating(user_id: str, movie_id: int, rating: float)`, `.get_ratings(user_id) -> dict[int, float]`; raises `StoreUnavailable` on botocore connection errors.

- [ ] Tests with `moto.mock_aws`: put/get; overwrite; separate users isolated; Decimal round-trip to float.
- [ ] Fail → implement → pass → commit.

### Task 4: API + model loader

**Files:** Create `app/model_loader.py`, `app/main.py`, `tests/test_api.py`

**Interfaces — Consumes:** Tasks 2–3. **Produces:** `app.main.create_app(recommender, store) -> FastAPI`, module-level `app` (lazy env-config), `handler = Mangum(app)`; `model_loader.load_model() -> dict`.

- [ ] Tests (TestClient, tiny model, moto store): every endpoint in spec table; 404 unknown movie (similar + rate); 422 bad rating / bad user id; 503 when store raises `StoreUnavailable`.
- [ ] Fail → implement → pass → commit.

### Task 5: Frontend

**Files:** Create `frontend/index.html`, `frontend/app.js`, `frontend/style.css`, `frontend/config.js`

- [ ] Build page per spec flow; manually verify in browser against local server with real model. Commit.

### Task 6: Infra, scripts, docs

**Files:** Create `docker-compose.yml`, `template.yaml`, `scripts/deploy.sh`, `scripts/run-local.sh`, `README.md`, `docs/architecture.md`

- [ ] `docker compose up -d` + `run-local.sh` end-to-end smoke test via curl. Validate template YAML parses. Commit.
