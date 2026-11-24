from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_optional_current_user
from app.db.database import get_db
from app.db.models import User
from app.repositories.profile_repository import (
    get_profile,
    get_user_ratings,
    get_user_reviews,
    update_profile,
)
from app.schemas.reviews import ReviewPage
from app.schemas.users import (
    ProfileResponse,
    ProfileUpdate,
    PublicProfileResponse,
    UserRatingPage,
)

router = APIRouter(prefix="/users", tags=["users"])
Username = Annotated[str, Path(min_length=4, max_length=20)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
OptionalUser = Annotated[User | None, Depends(get_optional_current_user)]
PageNumber = Annotated[int, Query(ge=1, le=2147483647)]
OPTIONAL_SECURITY = {"security": [{}, {"HTTPBearer": []}]}
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


@router.patch("/me/profile", response_model=ProfileResponse)
async def patch_profile(
    changes: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    session: DatabaseSession,
    response: Response,
) -> ProfileResponse:
    profile = await update_profile(session, user.id, changes)
    if profile is None:
        raise HTTPException(404, "Профиль не найден", headers=PRIVATE_HEADERS)
    await session.commit()
    response.headers.update(PRIVATE_HEADERS)
    return ProfileResponse(
        id=user.id,
        username=user.username,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        is_private=profile.is_private,
    )


@router.get("/{username}", openapi_extra=OPTIONAL_SECURITY)
async def read_profile(
    username: Username,
    viewer: OptionalUser,
    session: DatabaseSession,
    response: Response,
) -> ProfileResponse | PublicProfileResponse:
    profile = await get_profile(session, username, viewer.id if viewer else None)
    if profile is None:
        raise HTTPException(404, "Профиль не найден", headers=PRIVATE_HEADERS)
    response.headers.update(PRIVATE_HEADERS)
    return profile


@router.get("/{username}/ratings", openapi_extra=OPTIONAL_SECURITY)
async def read_user_ratings(
    username: Username,
    viewer: OptionalUser,
    session: DatabaseSession,
    response: Response,
    page: PageNumber = 1,
) -> UserRatingPage:
    ratings = await get_user_ratings(
        session, username, viewer.id if viewer else None, page=page
    )
    if ratings is None:
        raise HTTPException(404, "Раздел профиля не найден", headers=PRIVATE_HEADERS)
    response.headers.update(PRIVATE_HEADERS)
    return ratings


@router.get("/{username}/reviews", openapi_extra=OPTIONAL_SECURITY)
async def read_user_reviews(
    username: Username,
    viewer: OptionalUser,
    session: DatabaseSession,
    response: Response,
    page: PageNumber = 1,
) -> ReviewPage:
    reviews = await get_user_reviews(
        session, username, viewer.id if viewer else None, page=page
    )
    if reviews is None:
        raise HTTPException(404, "Раздел профиля не найден", headers=PRIVATE_HEADERS)
    response.headers.update(PRIVATE_HEADERS)
    return reviews
