# Architecture

```mermaid
flowchart LR
    user([Browser])
    subgraph AWS
        site[S3 static website<br/>index.html · app.js]
        api[API Gateway<br/>HTTP API]
        fn[Lambda<br/>FastAPI + Mangum]
        db[(DynamoDB<br/>Library table)]
        cognito[Cognito<br/>user pool]
        model[S3 model bucket<br/>model.json.gz]
        logs[CloudWatch Logs]
    end
    tmdb[(TMDB API)] -- enrich.py, offline --> train
    train[train.py<br/>run offline] -- upload --> model
    tmdbimg[TMDB image CDN]
    user -- poster & backdrop images --> tmdbimg
    user -- loads page --> site
    user -- sign up / sign in --> cognito
    user -- fetch /api/... + token --> api --> fn
    api -. checks token with .-> cognito
    fn -- read/write lists --> db
    fn -- load once per cold start --> model
    fn -. logs .-> logs
```

## What each AWS service does

| Service | Role in this project | Why this choice |
|---|---|---|
| **S3 (website bucket)** | Hosts the HTML/CSS/JS page as a static website. | No server needed for static files; pennies per month. |
| **API Gateway (HTTP API)** | Public HTTPS endpoint; forwards every `/api/...` request to Lambda. Its **JWT authorizer** rejects `/api/me/*` requests without a valid Cognito token before the Lambda runs. | Managed, scales automatically, free tier covers 1M requests/month. Auth is checked at the edge, not in our code. |
| **Cognito (user pool)** | Accounts: sign-up with email + password, email verification code, sign-in, tokens. | Passwords never touch our code or database; free for the first 10,000 monthly users. |
| **Lambda** | Runs the Python API (FastAPI wrapped by Mangum). | Pay per request, no idle cost, no servers to patch. |
| **DynamoDB** | Stores each user's list: one item per movie with its status and/or rating (`userId` partition key = Cognito user id, `movieId` sort key). | Serverless key-value store; "get one user's whole list" is a single query. |
| **S3 (model bucket)** | Holds the trained model file, private. | Decouples training from serving: retrain and re-upload without redeploying code. |
| **IAM** | The Lambda role may only use *this* table and read *this* bucket. | Least privilege. |
| **CloudFormation / SAM** | `template.yaml` creates all of the above in one command. | Infrastructure as code: repeatable, reviewable, deletable. |
| **CloudWatch Logs** | Lambda logs, automatically. | Debugging in production. |

## Local vs AWS

The same code runs in both places; only environment variables change.

| Piece | Locally | On AWS |
|---|---|---|
| Website | served by uvicorn from `frontend/` | S3 static website |
| API | `uvicorn app.server:app` | Lambda `app.server.handler` behind API Gateway |
| Lists | DynamoDB Local (official Amazon Docker image) | DynamoDB |
| Accounts | built-in: `LocalUsers` table, scrypt-hashed passwords, HMAC-signed tokens (`AUTH_MODE=local`) | Cognito + API Gateway JWT authorizer (`AUTH_MODE=cognito`) |
| Model | `model/model.json.gz` on disk (`MODEL_PATH`) | S3 (`MODEL_S3_BUCKET`), cached in `/tmp` |

## Movie details and images

`enrich.py` runs once on the developer's machine. It looks up each MovieLens movie on TMDB (MovieLens ships the TMDB id in `links.csv`), keeps only what the site shows (poster and backdrop paths, overview, tagline, runtime, director, top-5 cast) and `train.py` folds that into the model file. The browser then loads images straight from TMDB's image CDN.

Keeping this offline means the TMDB key never leaves the developer's machine, the Lambda makes no third-party calls (fast, nothing to rate-limit) and there is still nothing to change in the AWS setup.

## Accounts and sign-in

```mermaid
sequenceDiagram
    participant B as Browser
    participant C as Cognito
    participant G as API Gateway
    participant L as Lambda
    B->>C: SignUp(email, password)
    C-->>B: emails a 6-digit code
    B->>C: ConfirmSignUp(code), then InitiateAuth(email, password)
    C-->>B: ID token (1 h) + refresh token (30 days)
    B->>G: GET /api/me/library, Authorization: Bearer <ID token>
    G->>G: JWT authorizer: signature, issuer, audience, expiry
    G->>L: request + verified claims (sub = user id)
    L-->>B: that user's list
```

- The website calls Cognito directly over HTTPS with `fetch` (no SDK). It uses the `USER_PASSWORD_AUTH` flow; the password goes only to Cognito, never to our API.
- Browsing, search and movie pages are public. Everything personal lives under `/api/me/*`, the only routes with the authorizer. The Lambda takes the user id from the claims API Gateway verified, never from the URL, so one user can't read another's list.
- When the ID token is about to expire, the website swaps the refresh token for a new one; after 30 days you sign in again.
- Locally there is no API Gateway, so `AUTH_MODE=local` swaps in a small account system with the same shape. The server refuses to start in local mode on Lambda.

## Movie lists

Each movie on your list has a status (*plan to watch*, *watching*, *watched*, *dropped*) and optionally a rating. Rating a movie you hadn't listed, or had only planned to watch, marks it watched. The list feeds recommendations: listed movies are never recommended back to you, and a movie you dropped without rating counts like a 2★ rating. The "My list" page adds stats computed from the same data: movies watched, hours watched (TMDB runtimes), average rating and your three most-watched genres.

## How the recommendations work

1. **Offline training** (`train.py`, MovieLens: 9,742 movies, 100,836 ratings by 610 users):
   - *Content similarity:* each movie becomes a TF-IDF vector of its genres and user tags; cosine similarity between vectors.
   - *Collaborative similarity:* each movie becomes a vector of (mean-centred) ratings from every user; cosine similarity — "people who rated this highly also rated that highly". Only movies with ≥ 10 ratings take part.
   - *Hybrid:* `0.5 × content + 0.5 × collaborative`. Only the top 30 neighbours per movie are kept, so the model is ~1 MB instead of a 9,742 × 9,742 matrix.
   - *Popular list:* Bayesian average rating, so a film with two 5★ ratings doesn't beat one with hundreds of 4.5★.
2. **Serving** (`app/recommender.py`, `app/library.py`): for every movie the user rated, weight = rating − 3 (5★ → +2, 1★ → −2). Each neighbour's score is the sum of weight × similarity. Already-rated movies are removed; the biggest contributor becomes the "Because you liked …" reason. Users with no positive ratings get the popular list (cold start).

Because the heavy maths happens offline, the Lambda only needs FastAPI, Mangum and boto3 (34 MB package; Lambda's limit is 250 MB) and answers in milliseconds.
