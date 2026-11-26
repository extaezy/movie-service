from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin
from app.db.database import get_db
from app.db.models import Movie, User
from app.repositories.critic_review_repository import (
    InactiveCriticSourceError,
    create_critic_review,
    delete_critic_review,
    list_critic_reviews,
)
from app.schemas.critic_reviews import (
    CriticReviewCreate,
    CriticReviewPage,
    CriticReviewResponse,
    ReviewLanguage,
)

router = APIRouter(tags=["critic_reviews"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
MovieId = Annotated[int, Path(ge=1, le=2147483647)]
ReviewId = Annotated[int, Path(ge=1, le=2147483647)]
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


@router.get("/movies/{movie_id}/critic-reviews", response_model=CriticReviewPage)
async def get_movie_critic_reviews(
    movie_id: MovieId,
    session: DatabaseSession,
    response: Response,
    language: Annotated[ReviewLanguage | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
) -> CriticReviewPage:
    if await session.get(Movie, movie_id) is None:
        raise HTTPException(404, "Фильм не найден", headers=PRIVATE_HEADERS)
    reviews = await list_critic_reviews(session, movie_id, language=language, page=page)
    response.headers.update(PRIVATE_HEADERS)
    return reviews


@router.post(
    "/admin/critic-reviews", status_code=201, response_model=CriticReviewResponse
)
async def post_critic_review(
    entry: CriticReviewCreate,
    admin: CurrentAdmin,
    session: DatabaseSession,
    response: Response,
) -> CriticReviewResponse:
    if (
        await session.get(
            Movie, entry.movie_id, with_for_update={"read": True, "key_share": True}
        )
        is None
    ):
        raise HTTPException(404, "Фильм не найден", headers=PRIVATE_HEADERS)
    try:
        review = await create_critic_review(session, entry)
    except InactiveCriticSourceError as exc:
        await session.rollback()
        raise HTTPException(409, str(exc), headers=PRIVATE_HEADERS) from exc
    if review is None:
        await session.rollback()
        raise HTTPException(
            409, "Рецензия с такой ссылкой уже существует", headers=PRIVATE_HEADERS
        )
    await session.commit()
    response.headers.update(PRIVATE_HEADERS)
    return review


@router.delete("/admin/critic-reviews/{review_id}", status_code=204)
async def delete_critic_review_by_id(
    review_id: ReviewId, admin: CurrentAdmin, session: DatabaseSession
) -> Response:
    if not await delete_critic_review(session, review_id):
        raise HTTPException(404, "Рецензия не найдена", headers=PRIVATE_HEADERS)
    await session.commit()
    return Response(status_code=204, headers=PRIVATE_HEADERS)
