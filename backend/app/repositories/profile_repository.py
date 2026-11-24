from uuid import UUID

from sqlalchemy import Select, func, or_, select, true, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import Friendship, Profile, Rating, User, UserReview
from app.repositories.review_repository import REVIEW_PAGE_SIZE
from app.schemas.reviews import PublicReviewResponse, ReviewPage
from app.schemas.users import (
    ProfileResponse,
    ProfileUpdate,
    PublicProfileResponse,
    UserRatingPage,
    UserRatingResponse,
)

RATING_PAGE_SIZE = 20


def profile_access_condition(viewer_id: UUID | None) -> ColumnElement[bool]:
    access = Profile.is_private.is_(False)
    if viewer_id is None:
        return access
    accepted_friendship = (
        select(Friendship.id)
        .where(
            Friendship.user_low_id == func.least(User.id, viewer_id),
            Friendship.user_high_id == func.greatest(User.id, viewer_id),
            Friendship.status == "accepted",
        )
        .correlate(User)
        .exists()
    )
    return or_(access, User.id == viewer_id, accepted_friendship)


async def get_profile(
    session: AsyncSession, username: str, viewer_id: UUID | None
) -> ProfileResponse | PublicProfileResponse | None:
    statement = (
        select(
            User.id,
            User.username,
            Profile.display_name,
            Profile.bio,
            Profile.avatar_url,
            Profile.is_private,
            profile_access_condition(viewer_id).label("has_access"),
        )
        .join(Profile, Profile.user_id == User.id)
        .where(User.username == username)
    )
    row = (await session.execute(statement)).mappings().one_or_none()
    if row is None:
        return None
    if not row["has_access"]:
        return PublicProfileResponse(
            username=row["username"], avatar_url=row["avatar_url"]
        )
    return ProfileResponse.model_validate(row)


async def update_profile(
    session: AsyncSession, user_id: UUID, changes: ProfileUpdate
) -> Profile | None:
    statement = (
        update(Profile)
        .where(Profile.user_id == user_id)
        .values(**changes.model_dump(mode="json", exclude_unset=True))
        .returning(Profile)
    )
    return await session.scalar(statement)


async def get_visible_content_rows(
    session: AsyncSession,
    username: str,
    viewer_id: UUID | None,
    entries: Select,
    *,
    page: int,
    page_size: int,
    order_fields: tuple[str, str],
) -> list[RowMapping]:
    total_results = (
        entries.order_by(None).with_only_columns(func.count()).scalar_subquery()
    )
    page_entries = entries.offset((page - 1) * page_size).limit(page_size).lateral()
    statement = (
        select(page_entries, total_results.label("total_results"))
        .select_from(User)
        .join(Profile, Profile.user_id == User.id)
        .outerjoin(page_entries, true())
        .where(User.username == username, profile_access_condition(viewer_id))
        .order_by(*(page_entries.c[field].desc() for field in order_fields))
    )
    return list((await session.execute(statement)).mappings().all())


async def get_user_ratings(
    session: AsyncSession, username: str, viewer_id: UUID | None, *, page: int
) -> UserRatingPage | None:
    entries = (
        select(Rating.movie_id, Rating.score, Rating.created_at, Rating.updated_at)
        .where(Rating.user_id == User.id)
        .correlate(User)
        .order_by(Rating.updated_at.desc(), Rating.movie_id.desc())
    )
    rows = await get_visible_content_rows(
        session,
        username,
        viewer_id,
        entries,
        page=page,
        page_size=RATING_PAGE_SIZE,
        order_fields=("updated_at", "movie_id"),
    )
    if not rows:
        return None
    count = rows[0]["total_results"]
    results = [
        UserRatingResponse.model_validate(row)
        for row in rows
        if row["movie_id"] is not None
    ]
    return UserRatingPage(
        page=page,
        page_size=RATING_PAGE_SIZE,
        total_results=count,
        total_pages=(count + RATING_PAGE_SIZE - 1) // RATING_PAGE_SIZE,
        results=results,
    )


async def get_user_reviews(
    session: AsyncSession, username: str, viewer_id: UUID | None, *, page: int
) -> ReviewPage | None:
    entries = (
        select(
            UserReview.id,
            UserReview.movie_id,
            UserReview.text,
            UserReview.contains_spoilers,
            UserReview.created_at,
            User.username.label("author_username"),
        )
        .where(UserReview.user_id == User.id)
        .correlate(User)
        .order_by(UserReview.created_at.desc(), UserReview.id.desc())
    )
    rows = await get_visible_content_rows(
        session,
        username,
        viewer_id,
        entries,
        page=page,
        page_size=REVIEW_PAGE_SIZE,
        order_fields=("created_at", "id"),
    )
    if not rows:
        return None
    count = rows[0]["total_results"]
    results = [
        PublicReviewResponse.model_validate(row)
        for row in rows
        if row["id"] is not None
    ]
    return ReviewPage(
        page=page,
        page_size=REVIEW_PAGE_SIZE,
        total_results=count,
        total_pages=(count + REVIEW_PAGE_SIZE - 1) // REVIEW_PAGE_SIZE,
        results=results,
    )
