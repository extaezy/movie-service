from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.repositories.review_repository import delete_review, update_review
from app.schemas.reviews import ReviewUpdate, ReviewUpdateResponse

router = APIRouter(prefix="/reviews", tags=["reviews"])
ReviewId = Annotated[int, Path(ge=1, le=2147483647)]


@router.patch("/{review_id}", response_model=ReviewUpdateResponse)
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


@router.delete("/{review_id}", status_code=204)
async def delete_review_by_id(
    review_id: ReviewId,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    if not await delete_review(session, user.id, review_id):
        raise HTTPException(404, "Рецензия не найдена")
    await session.commit()
    return Response(status_code=204)
