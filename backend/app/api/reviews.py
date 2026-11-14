from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import Movie, User
from app.repositories.review_repository import (
    create_review,
    delete_review,
    list_movie_reviews,
    update_review,
)
from app.schemas.reviews import (
    ReviewCreate,
    ReviewPage,
    ReviewResponse,
    ReviewUpdate,
    ReviewUpdateResponse,
)

router = APIRouter(tags=["reviews"])
MovieId = Annotated[int, Path(ge=1, le=2147483647)]
ReviewId = Annotated[int, Path(ge=1, le=2147483647)]


@router.get("/movies/{movie_id}/reviews", response_model=ReviewPage)
async def get_movie_reviews(
    movie_id: MovieId,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
) -> ReviewPage:
    if await session.get(Movie, movie_id) is None:
        raise HTTPException(404, "Фильм не найден")
    return await list_movie_reviews(session, movie_id, page=page)


@router.post(
    "/movies/{movie_id}/reviews", status_code=201, response_model=ReviewResponse
)
async def post_movie_review(
    movie_id: MovieId,
    review: ReviewCreate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
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


@router.patch("/reviews/{review_id}", response_model=ReviewUpdateResponse)
async def patch_review(
    review_id: ReviewId,
    changes: ReviewUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ReviewUpdateResponse:
    review = await update_review(session, user.id, review_id, changes)
    if review is None:
        raise HTTPException(404, "Рецензия не найдена")
    await session.commit()
    return ReviewUpdateResponse.model_validate(review)


@router.delete("/reviews/{review_id}", status_code=204)
async def delete_review_by_id(
    review_id: ReviewId,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    if not await delete_review(session, user.id, review_id):
        raise HTTPException(404, "Рецензия не найдена")
    await session.commit()
    return Response(status_code=204)
