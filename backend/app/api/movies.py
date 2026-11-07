from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.integrations.tmdb import TMDBSearchResult, open_tmdb_client
from app.repositories.movie_repository import (
    get_movie_by_id,
    get_movie_by_tmdb_id,
    save_movie,
)
from app.schemas.movies import MovieResponse

router = APIRouter(prefix="/movies", tags=["movies"])
MovieId = Annotated[int, Path(ge=1, le=2147483647)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/search", response_model=TMDBSearchResult, response_model_by_alias=False)
async def search_movies(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    page: Annotated[int, Query(ge=1, le=500)] = 1,
):
    if not q.strip():
        raise HTTPException(422, "Название фильма не должно быть пустым")
    async with open_tmdb_client() as client:
        return await client.search_movies(q, page)


@router.get("/tmdb/{tmdb_id}", response_model=MovieResponse)
async def open_movie(tmdb_id: MovieId, session: DatabaseSession):
    async with session.begin():
        existing = await get_movie_by_tmdb_id(session, tmdb_id)
    if existing is not None:
        return existing
    async with open_tmdb_client() as client:
        details = await client.get_movie(tmdb_id)
    async with session.begin():
        return await save_movie(session, details)


@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie(movie_id: MovieId, session: DatabaseSession):
    movie = await get_movie_by_id(session, movie_id)
    if movie is None:
        raise HTTPException(404, "Фильм не найден")
    return movie
