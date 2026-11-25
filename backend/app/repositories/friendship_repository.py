from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Friendship, Profile, User
from app.schemas.friendships import (
    FriendPage,
    FriendRequestPage,
    FriendshipDecision,
    FriendUserResponse,
    IncomingFriendRequest,
)

FRIEND_PAGE_SIZE = 20


async def create_friend_request(
    session: AsyncSession, sender_id: UUID, recipient_id: UUID
) -> Friendship | None:
    statement = (
        insert(Friendship)
        .values(
            user_low_id=min(sender_id, recipient_id),
            user_high_id=max(sender_id, recipient_id),
            requested_by_id=sender_id,
            status="pending",
        )
        .on_conflict_do_update(
            constraint="uq_friendships_pair",
            set_={
                "requested_by_id": sender_id,
                "status": "pending",
                "created_at": func.now(),
                "updated_at": func.now(),
            },
            where=Friendship.status == "rejected",
        )
        .returning(Friendship)
    )
    return await session.scalar(statement)


async def decide_friend_request(
    session: AsyncSession,
    recipient_id: UUID,
    request_id: int,
    decision: FriendshipDecision,
) -> Friendship | None:
    statement = (
        update(Friendship)
        .where(
            Friendship.id == request_id,
            Friendship.status == "pending",
            Friendship.requested_by_id != recipient_id,
            or_(
                Friendship.user_low_id == recipient_id,
                Friendship.user_high_id == recipient_id,
            ),
        )
        .values(status=decision, updated_at=func.now())
        .returning(Friendship)
    )
    return await session.scalar(statement)


async def remove_friend(session: AsyncSession, user_id: UUID, friend_id: UUID) -> bool:
    statement = (
        delete(Friendship)
        .where(
            Friendship.user_low_id == min(user_id, friend_id),
            Friendship.user_high_id == max(user_id, friend_id),
            Friendship.status == "accepted",
        )
        .returning(Friendship.id)
    )
    return await session.scalar(statement) is not None


async def list_incoming_requests(
    session: AsyncSession, user_id: UUID, *, page: int
) -> FriendRequestPage:
    incoming = (
        Friendship.status == "pending",
        Friendship.requested_by_id != user_id,
        or_(Friendship.user_low_id == user_id, Friendship.user_high_id == user_id),
    )
    count = (
        await session.scalar(
            select(func.count()).select_from(Friendship).where(*incoming)
        )
        or 0
    )
    statement = (
        select(
            Friendship.id,
            Friendship.created_at,
            User.id.label("sender_id"),
            User.username,
            Profile.avatar_url,
        )
        .select_from(Friendship)
        .join(User, User.id == Friendship.requested_by_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(*incoming)
        .order_by(Friendship.created_at.desc(), Friendship.id.desc())
        .offset((page - 1) * FRIEND_PAGE_SIZE)
        .limit(FRIEND_PAGE_SIZE)
    )
    rows = (await session.execute(statement)).mappings().all()
    return FriendRequestPage(
        page=page,
        page_size=FRIEND_PAGE_SIZE,
        total_results=count,
        total_pages=(count + FRIEND_PAGE_SIZE - 1) // FRIEND_PAGE_SIZE,
        results=[
            IncomingFriendRequest(
                id=row["id"],
                created_at=row["created_at"],
                sender=FriendUserResponse(
                    id=row["sender_id"],
                    username=row["username"],
                    avatar_url=row["avatar_url"],
                ),
            )
            for row in rows
        ],
    )


async def list_friends(
    session: AsyncSession, user_id: UUID, *, page: int
) -> FriendPage:
    accepted = (
        Friendship.status == "accepted",
        or_(Friendship.user_low_id == user_id, Friendship.user_high_id == user_id),
    )
    count = (
        await session.scalar(
            select(func.count()).select_from(Friendship).where(*accepted)
        )
        or 0
    )
    friend_id = case(
        (Friendship.user_low_id == user_id, Friendship.user_high_id),
        else_=Friendship.user_low_id,
    )
    statement = (
        select(User.id, User.username, Profile.avatar_url)
        .select_from(Friendship)
        .join(User, User.id == friend_id)
        .outerjoin(Profile, Profile.user_id == User.id)
        .where(*accepted)
        .order_by(User.username.asc(), User.id.asc())
        .offset((page - 1) * FRIEND_PAGE_SIZE)
        .limit(FRIEND_PAGE_SIZE)
    )
    rows = (await session.execute(statement)).mappings().all()
    return FriendPage(
        page=page,
        page_size=FRIEND_PAGE_SIZE,
        total_results=count,
        total_pages=(count + FRIEND_PAGE_SIZE - 1) // FRIEND_PAGE_SIZE,
        results=[FriendUserResponse.model_validate(row) for row in rows],
    )
