from uuid import UUID

from sqlalchemy import delete, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserReview
from app.schemas.reviews import ReviewUpdate


async def create_review(
    session: AsyncSession,
    *,
    user_id: UUID,
    movie_id: int,
    text: str,
    contains_spoilers: bool,
) -> UserReview | None:
    statement = (
        insert(UserReview)
        .values(
            user_id=user_id,
            movie_id=movie_id,
            text=text,
            contains_spoilers=contains_spoilers,
        )
        .on_conflict_do_nothing(constraint="uq_user_reviews_user_movie")
        .returning(UserReview)
    )
    return await session.scalar(statement)


async def delete_review(session: AsyncSession, user_id: UUID, review_id: int) -> bool:
    statement = (
        delete(UserReview)
        .where(UserReview.id == review_id, UserReview.user_id == user_id)
        .returning(UserReview.id)
    )
    return await session.scalar(statement) is not None


async def update_review(
    session: AsyncSession, user_id: UUID, review_id: int, changes: ReviewUpdate
) -> UserReview | None:
    statement = (
        update(UserReview)
        .where(UserReview.id == review_id, UserReview.user_id == user_id)
        .values(**changes.model_dump(exclude_unset=True), updated_at=func.now())
        .returning(UserReview)
    )
    return await session.scalar(statement)
