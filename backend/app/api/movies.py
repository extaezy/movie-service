from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Movie, User
from app.integrations.tmdb import (
    TMDB_MAX_PAGE,
    TMDBDiscoverSort,
    TMDBSearchResult,
    open_tmdb_client,
)
from app.repositories.movie_repository import (
    get_movie_by_id,
    get_movie_by_tmdb_id,
    list_movies,
    save_movie,
)
from app.repositories.rating_repository import delete_rating, upsert_rating
from app.repositories.review_repository import create_review
from app.schemas.movies import MovieDetailResponse, MoviePage, MovieSort
from app.schemas.ratings import RatingResponse, RatingUpdate
from app.schemas.reviews import ReviewCreate, ReviewResponse

router = APIRouter(prefix="/movies", tags=["movies"])
MovieId = Annotated[int, Path(ge=1, le=2147483647)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=MoviePage)
async def get_catalog(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
    genre_id: Annotated[int | None, Query(ge=1, le=2147483647)] = None,
    year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    sort: MovieSort = "release_date_desc",
) -> MoviePage:
    return await list_movies(
        session, page=page, genre_id=genre_id, year=year, sort=sort
    )


@router.get("/discover", response_model=TMDBSearchResult, response_model_by_alias=False)
async def discover_movies(
    page: Annotated[int, Query(ge=1, le=TMDB_MAX_PAGE)] = 1,
    tmdb_genre_id: Annotated[int | None, Query(ge=1, le=2147483647)] = None,
    year: Annotated[int | None, Query(ge=1, le=9999)] = None,
    sort: TMDBDiscoverSort = "popularity_desc",
) -> TMDBSearchResult:
    async with open_tmdb_client() as client:
        return await client.discover_movies(
            page=page, tmdb_genre_id=tmdb_genre_id, year=year, sort=sort
        )


@router.get("/search", response_model=TMDBSearchResult, response_model_by_alias=False)
async def search_movies(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    page: Annotated[int, Query(ge=1, le=TMDB_MAX_PAGE)] = 1,
):
    if not q.strip():
        raise HTTPException(422, "Название фильма не должно быть пустым")
    async with open_tmdb_client() as client:
        return await client.search_movies(q, page)


@router.get("/tmdb/{tmdb_id}", response_model=MovieDetailResponse)
async def open_movie(tmdb_id: MovieId, session: DatabaseSession):
    async with session.begin():
        existing = await get_movie_by_tmdb_id(session, tmdb_id)
    if existing is not None:
        return existing
    async with open_tmdb_client() as client:
        details = await client.get_movie(tmdb_id)
    async with session.begin():
        return await save_movie(session, details)


@router.get("/{movie_id}", response_model=MovieDetailResponse)
async def get_movie(movie_id: MovieId, session: DatabaseSession):
    movie = await get_movie_by_id(session, movie_id)
    if movie is None:
        raise HTTPException(404, "Фильм не найден")
    return movie


@router.put("/{movie_id}/rating", response_model=RatingResponse)
async def put_movie_rating(
    movie_id: MovieId,
    rating: RatingUpdate,
    user: CurrentUser,
    session: DatabaseSession,
) -> RatingResponse:
    if (
        await session.get(
            Movie, movie_id, with_for_update={"read": True, "key_share": True}
        )
        is None
    ):
        raise HTTPException(404, "Фильм не найден")
    await upsert_rating(session, user.id, movie_id, rating.score)
    await session.commit()
    return RatingResponse(movie_id=movie_id, score=rating.score)


@router.delete("/{movie_id}/rating", status_code=204)
async def delete_movie_rating(
    movie_id: MovieId, user: CurrentUser, session: DatabaseSession
) -> Response:
    if await session.get(Movie, movie_id) is None:
        raise HTTPException(404, "Фильм не найден")
    await delete_rating(session, user.id, movie_id)
    await session.commit()
    return Response(status_code=204)


@router.post("/{movie_id}/reviews", status_code=201, response_model=ReviewResponse)
async def post_movie_review(
    movie_id: MovieId,
    review: ReviewCreate,
    user: CurrentUser,
    session: DatabaseSession,
) -> ReviewResponse:
    if (
        await session.get(
            Movie, movie_id, with_for_update={"read": True, "key_share": True}
        )
        is None
    ):
        raise HTTPException(404, "Фильм не найден")
    created_review = await create_review(
        session,
        user_id=user.id,
        movie_id=movie_id,
        text=review.text,
        contains_spoilers=review.contains_spoilers,
    )
    if created_review is None:
        raise HTTPException(409, "Вы уже написали рецензию на этот фильм")
    await session.commit()
    return ReviewResponse.model_validate(created_review)
