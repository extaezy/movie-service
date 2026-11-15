from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserReview
from app.schemas.reviews import PublicReviewResponse, ReviewPage, ReviewUpdate

REVIEW_PAGE_SIZE = 10


async def list_movie_reviews(
    session: AsyncSession, movie_id: int, *, page: int
) -> ReviewPage:
    movie_filter = UserReview.movie_id == movie_id
    total_results = (
        await session.scalar(
            select(func.count()).select_from(UserReview).where(movie_filter)
        )
        or 0
    )
    offset = (page - 1) * REVIEW_PAGE_SIZE
    review_page = ReviewPage(
        page=page,
        page_size=REVIEW_PAGE_SIZE,
        total_results=total_results,
        total_pages=(total_results + REVIEW_PAGE_SIZE - 1) // REVIEW_PAGE_SIZE,
        results=[],
    )
    if offset >= total_results:
        return review_page

    statement = (
        select(
            UserReview.id,
            UserReview.movie_id,
            UserReview.text,
            UserReview.contains_spoilers,
            UserReview.created_at,
            User.username.label("author_username"),
        )
        .join(User, User.id == UserReview.user_id)
        .where(movie_filter)
        .order_by(UserReview.created_at.desc(), UserReview.id.desc())
        .offset(offset)
        .limit(REVIEW_PAGE_SIZE)
    )
    result = await session.execute(statement)
    review_page.results = [
        PublicReviewResponse.model_validate(row) for row in result.mappings()
    ]
    return review_page


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
