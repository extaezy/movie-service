import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuthSession, RefreshToken, User


class InvalidRefreshTokenError(Exception):
    pass


def refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def add_refresh_token(session: AsyncSession, session_id: UUID) -> str:
    token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(session_id=session_id, token_hash=refresh_token_hash(token))
    )
    return token


async def create_auth_session(
    session: AsyncSession, user_id: UUID
) -> tuple[AuthSession, str]:
    auth_session = AuthSession(
        user_id=user_id, expires_at=datetime.now(UTC) + timedelta(days=7)
    )
    session.add(auth_session)
    await session.flush()
    token = add_refresh_token(session, auth_session.id)
    await session.commit()
    return auth_session, token


async def get_active_auth_session(
    session: AsyncSession, session_id: UUID, user_id: UUID
) -> AuthSession | None:
    return await session.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )


async def find_refresh_session(session: AsyncSession, token: str) -> AuthSession | None:
    if len(token) != 64:
        return None
    session_id = await session.scalar(
        select(RefreshToken.session_id).where(
            RefreshToken.token_hash == refresh_token_hash(token)
        )
    )
    if session_id is None:
        return None
    return await session.scalar(
        select(AuthSession).where(AuthSession.id == session_id).with_for_update()
    )


async def rotate_refresh_token(
    session: AsyncSession, token: str
) -> tuple[AuthSession, str]:
    auth_session = await find_refresh_session(session, token)
    now = datetime.now(UTC)
    if auth_session is None:
        raise InvalidRefreshTokenError
    if auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise InvalidRefreshTokenError
    refresh = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == refresh_token_hash(token))
    )
    active = await session.scalar(
        select(User.is_active).where(User.id == auth_session.user_id)
    )
    if refresh.used_at is not None or not active:
        auth_session.revoked_at = now
        await session.commit()
        raise InvalidRefreshTokenError
    refresh.used_at = now
    replacement = add_refresh_token(session, auth_session.id)
    await session.commit()
    return auth_session, replacement
