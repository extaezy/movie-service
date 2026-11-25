from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.repositories.friendship_repository import (
    create_friend_request,
    decide_friend_request,
    list_friends,
    list_incoming_requests,
    remove_friend,
)
from app.schemas.friendships import (
    FriendPage,
    FriendRequestPage,
    FriendshipResponse,
)

router = APIRouter(prefix="/friends", tags=["friends"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
RequestId = Annotated[int, Path(ge=1, le=2147483647)]
PageNumber = Annotated[int, Query(ge=1, le=2147483647)]
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


@router.post("/requests/{user_id}", status_code=201)
async def send_friend_request(
    user_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
) -> FriendshipResponse:
    if user_id == user.id:
        raise HTTPException(
            400, "Нельзя отправить заявку самому себе", headers=PRIVATE_HEADERS
        )
    recipient = await session.get(
        User, user_id, with_for_update={"read": True, "key_share": True}
    )
    if recipient is None or not recipient.is_active:
        raise HTTPException(404, "Пользователь не найден", headers=PRIVATE_HEADERS)
    friendship = await create_friend_request(session, user.id, user_id)
    if friendship is None:
        raise HTTPException(
            409,
            "Заявка уже существует или дружба уже подтверждена",
            headers=PRIVATE_HEADERS,
        )
    await session.commit()
    response.headers.update(PRIVATE_HEADERS)
    return FriendshipResponse.model_validate(friendship)


@router.get("/requests")
async def get_incoming_friend_requests(
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
    page: PageNumber = 1,
) -> FriendRequestPage:
    requests = await list_incoming_requests(session, user.id, page=page)
    response.headers.update(PRIVATE_HEADERS)
    return requests


@router.post("/requests/{request_id}/accept")
async def accept_friend_request(
    request_id: RequestId,
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
) -> FriendshipResponse:
    friendship = await decide_friend_request(session, user.id, request_id, "accepted")
    if friendship is None:
        raise HTTPException(404, "Входящая заявка не найдена", headers=PRIVATE_HEADERS)
    await session.commit()
    response.headers.update(PRIVATE_HEADERS)
    return FriendshipResponse.model_validate(friendship)


@router.post("/requests/{request_id}/reject")
async def reject_friend_request(
    request_id: RequestId,
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
) -> FriendshipResponse:
    friendship = await decide_friend_request(session, user.id, request_id, "rejected")
    if friendship is None:
        raise HTTPException(404, "Входящая заявка не найдена", headers=PRIVATE_HEADERS)
    await session.commit()
    response.headers.update(PRIVATE_HEADERS)
    return FriendshipResponse.model_validate(friendship)


@router.delete("/{user_id}", status_code=204)
async def delete_friend(
    user_id: UUID, user: CurrentUser, session: DatabaseSession
) -> Response:
    if user_id == user.id:
        raise HTTPException(400, "Нельзя удалить самого себя", headers=PRIVATE_HEADERS)
    removed = await remove_friend(session, user.id, user_id)
    if not removed:
        raise HTTPException(404, "Друг не найден", headers=PRIVATE_HEADERS)
    await session.commit()
    return Response(status_code=204, headers=PRIVATE_HEADERS)


@router.get("")
async def get_friends(
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
    page: PageNumber = 1,
) -> FriendPage:
    friends = await list_friends(session, user.id, page=page)
    response.headers.update(PRIVATE_HEADERS)
    return friends
