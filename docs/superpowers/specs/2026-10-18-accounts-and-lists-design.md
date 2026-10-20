# Movie Picks v3 — Accounts (Cognito) + movie lists — Design

**Date:** 2026-10-18
**Builds on:** `2026-10-15-ux-v2-design.md`

## Why

The project is judged by a professor who may find v2 too simple. v3 adds two
features a reviewer expects from a "real" app — sign-in and a personal movie
list — and one more AWS service (Amazon Cognito) wired in the AWS-native way.
The user handed the detailed choices to the builder; every choice below that
is not "accounts" or "watched / watching / plan to watch" is the builder's call.

### Goals

- Sign up / sign in with email + password. On AWS: Amazon Cognito user pool,
  email verification code, tokens checked by an API Gateway JWT authorizer
  before the Lambda runs.
- Runs locally with no AWS account: a small built-in account system stands in
  for Cognito (`AUTH_MODE=local`).
- A personal library: each movie can have a **status** — plan to watch,
  watching, watched, dropped — and a **rating**. Rating a movie you haven't
  listed marks it watched.
- "My list" page with status tabs and stats: watched count, hours watched,
  average rating, favourite genres.
- Lists feed recommendations: listed movies are never recommended, a dropped
  (unrated) movie counts like a 2★ rating.

### Non-goals

- Anonymous use of personal features (browsing/search/details stay public;
  rating and lists need an account). No migration of v2 anonymous ratings.
- Password reset, social login, profile pictures, display names, sharing lists.
- Cognito Hosted UI (needs HTTPS callback URLs; the S3 website is HTTP).

## Identity

| | AWS (`AUTH_MODE=cognito`) | Local (`AUTH_MODE=local`) |
|---|---|---|
| Who signs people up | Cognito user pool (username = email, email auto-verified by code, min 8-char password) | `/api/auth/local/signup` — scrypt-hashed password in DynamoDB Local table `LocalUsers` |
| Token | Cognito ID token (JWT), refreshed with the refresh token | HMAC-SHA256 signed token, 7 days |
| Who checks it | API Gateway JWT authorizer on `ANY /api/me/{proxy+}`; Lambda reads `sub` from the verified claims in the event | The app, on every `/api/me/*` request |
| User id | Cognito `sub` | random id stored with the account |

The browser talks to Cognito directly (`InitiateAuth` with `USER_PASSWORD_AUTH`,
`SignUp`, `ConfirmSignUp`, `ResendConfirmationCode`) over HTTPS with `fetch` —
no SDK, no build step. The Lambda never sees passwords.

Safety rules: local auth is refused on Lambda; in Cognito mode a request
without authorizer claims is 401 (routes outside `/api/me` have no claims).

## Data

DynamoDB table `Library` (replaces `Ratings`): PK `userId` (S), SK `movieId` (N),
attributes `status` (S, optional), `rating` (N, optional), `updatedAt` (ISO
string). Setting a rating does `status = if_not_exists(status, "watched")`.
Clearing a rating keeps the status. Removing from the list deletes the item.

## API (all `/api/me/*` → 401 without a valid sign-in)

| Method | Path | |
|---|---|---|
| POST | `/api/auth/local/signup` `{email, password}` | local mode only → 201 `{token, email}`; 409 taken; 422 invalid |
| POST | `/api/auth/local/login` | local mode only → `{token, email}`; 401 wrong |
| GET | `/api/me/library` | entries: movie summary + `status`, `rating`, `updated`; newest first |
| PUT | `/api/me/library/{id}/status` `{status}` | `plan_to_watch` / `watching` / `watched` / `dropped`; 404 unknown movie |
| PUT | `/api/me/library/{id}/rating` `{rating}` | 0.5–5; marks watched if unlisted |
| DELETE | `/api/me/library/{id}/rating` | 204, status kept |
| DELETE | `/api/me/library/{id}` | 204, removed from list |
| GET | `/api/me/recommendations` | as before, from the library |
| GET | `/api/me/stats` | `{counts, rated, averageRating, minutesWatched, topGenres}` |

The v2 `/api/users/{id}/*` endpoints are removed.

## Frontend

- Top bar: signed out → "Sign in"; signed in → "My list (n)" + account menu
  (email, Sign out).
- `#/signin`, `#/signup` (+ code step on Cognito). After sign-up → welcome
  picker. Signing out returns to home.
- Movie page: "Your list" panel — four status buttons, remove, stars. Signed
  out: a prompt to sign in.
- Home signed in: hero, "Continue watching", "Top picks for you", "Because you
  liked X", "On your watchlist", "Popular". Signed out: hero, sign-up nudge,
  popular.
- `#/list?status=…`: stats strip, status tabs with counts, grid with a status
  menu and stars per movie. `#/ratings` redirects here.
- Cards show a small status badge for listed movies.

## AWS changes (template.yaml)

`UserPool`, `UserPoolClient` (no secret, `USER_PASSWORD_AUTH` +
`REFRESH_TOKEN_AUTH`, prevent user-existence errors), explicit `HttpApi` with
CORS config and a Cognito JWT authorizer, `LibraryTable`. Outputs gain
`UserPoolId`, `UserPoolClientId`. `deploy.sh` writes them into `config.js`.

## Testing

- Storage (moto): status/rating combinations, if_not_exists, removal.
- Local auth: hashing, wrong password, duplicate email, token tamper/expiry.
- API: 401s, every `/api/me` endpoint, Cognito claims read from a Mangum
  API Gateway event, local endpoints absent in Cognito mode.
- Frontend: headless walkthrough in local mode; the Cognito browser calls
  exercised against `moto_server`'s Cognito emulation.
