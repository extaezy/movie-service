from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile, User


class UserAlreadyExistsError(Exception):
    pass


async def create_user(
    session: AsyncSession, username: str, email: str, hashed_password: str
) -> User:
    user = User(username=username, email=email, hashed_password=hashed_password)
    try:
        async with session.begin():
            session.add(user)
            await session.flush()
            session.add(Profile(user_id=user.id))
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise UserAlreadyExistsError(
                "Email или username уже зарегистрирован"
            ) from exc
        raise
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.get(User, user_id)
