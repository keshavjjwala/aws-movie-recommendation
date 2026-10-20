"""HTTP API. `create_app` receives its dependencies, so tests can pass fakes;
app/server.py wires up the real ones from environment variables.

Everything under /api/me needs a signed-in user (see app/auth.py)."""

from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import AuthError
from app.library import stats, taste
from app.storage import StoreUnavailable

Limit = Query(20, ge=1, le=100)


class RatingIn(BaseModel):
    rating: float = Field(ge=0.5, le=5.0)


class StatusIn(BaseModel):
    status: Literal["plan_to_watch", "watching", "watched", "dropped"]


class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


def create_app(recommender, store, auth, frontend_dir=None):
    app = FastAPI(title="Movie Recommender")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"]
    )

    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(request: Request, exc: StoreUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(AuthError)
    async def auth_error(request: Request, exc: AuthError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    def current_user(request: Request):
        user = auth.user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to use your list.", headers={"WWW-Authenticate": "Bearer"})
        return user

    def require_movie(movie_id):
        movie = recommender.movie(movie_id)
        if movie is None:
            raise HTTPException(status_code=404, detail=f"Unknown movie id {movie_id}")
        return movie

    @app.get("/api/movies/search")
    def search(q: str = Query(min_length=1), limit: int = Limit):
        return recommender.search(q, limit)

    @app.get("/api/movies/popular")
    def popular(limit: int = Limit):
        return recommender.popular(limit)

    @app.get("/api/movies/{movie_id}")
    def details(movie_id: int):
        require_movie(movie_id)
        return recommender.details(movie_id)

    @app.get("/api/movies/{movie_id}/similar")
    def similar(movie_id: int, limit: int = Query(10, ge=1, le=30)):
        require_movie(movie_id)
        return recommender.similar(movie_id, limit)

    if hasattr(auth, "sign_up"):  # local stand-in for Cognito; absent on AWS

        @app.post("/api/auth/local/signup", status_code=201)
        def sign_up(body: Credentials):
            return auth.sign_up(body.email, body.password)

        @app.post("/api/auth/local/login")
        def sign_in(body: Credentials):
            return auth.sign_in(body.email, body.password)

    @app.get("/api/me/library")
    def library(user=Depends(current_user)):
        entries = [
            {**recommender.movie(i), **e} for i, e in store.get_library(user["id"]).items() if recommender.movie(i)
        ]
        return sorted(entries, key=lambda m: m["updated"], reverse=True)

    @app.put("/api/me/library/{movie_id}/status")
    def set_status(movie_id: int, body: StatusIn, user=Depends(current_user)):
        require_movie(movie_id)
        store.set_status(user["id"], movie_id, body.status)
        return {"movieId": movie_id, "status": body.status}

    @app.put("/api/me/library/{movie_id}/rating")
    def rate(movie_id: int, body: RatingIn, user=Depends(current_user)):
        require_movie(movie_id)
        store.set_rating(user["id"], movie_id, body.rating)
        return {"movieId": movie_id, "rating": body.rating}

    @app.delete("/api/me/library/{movie_id}/rating", status_code=204)
    def unrate(movie_id: int, user=Depends(current_user)):
        store.clear_rating(user["id"], movie_id)
        return Response(status_code=204)

    @app.delete("/api/me/library/{movie_id}", status_code=204)
    def remove(movie_id: int, user=Depends(current_user)):
        store.remove(user["id"], movie_id)
        return Response(status_code=204)

    @app.get("/api/me/recommendations")
    def recommendations(limit: int = Limit, user=Depends(current_user)):
        library = store.get_library(user["id"])
        return recommender.recommend(taste(library), limit, exclude=library.keys())

    @app.get("/api/me/stats")
    def profile_stats(user=Depends(current_user)):
        return stats(store.get_library(user["id"]), recommender)

    if frontend_dir is not None:
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app
