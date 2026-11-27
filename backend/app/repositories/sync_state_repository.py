from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalSyncState

NYT_SYNC_NAME = "nyt_daily_reviews"
LEASE_DURATION = timedelta(minutes=30)


async def acquire_nyt_sync_lease(session: AsyncSession, token: UUID) -> bool:
    await session.execute(
        insert(ExternalSyncState).values(name=NYT_SYNC_NAME).on_conflict_do_nothing()
    )
    acquired = await session.scalar(
        update(ExternalSyncState)
        .where(
            ExternalSyncState.name == NYT_SYNC_NAME,
            or_(
                ExternalSyncState.lease_expires_at.is_(None),
                ExternalSyncState.lease_expires_at <= func.now(),
            ),
        )
        .values(lease_token=token, lease_expires_at=func.now() + LEASE_DURATION)
        .returning(ExternalSyncState.name)
    )
    await session.commit()
    return acquired is not None


async def renew_nyt_sync_lease(session: AsyncSession, token: UUID) -> ExternalSyncState:
    state = await session.scalar(
        update(ExternalSyncState)
        .where(
            ExternalSyncState.name == NYT_SYNC_NAME,
            ExternalSyncState.lease_token == token,
            ExternalSyncState.lease_expires_at > func.now(),
        )
        .values(lease_expires_at=func.now() + LEASE_DURATION)
        .returning(ExternalSyncState)
    )
    if state is None:
        raise RuntimeError("NYT sync lease expired")
    return state


async def release_nyt_sync_lease(session: AsyncSession, token: UUID) -> None:
    await session.execute(
        update(ExternalSyncState)
        .where(
            ExternalSyncState.name == NYT_SYNC_NAME,
            ExternalSyncState.lease_token == token,
        )
        .values(lease_token=None, lease_expires_at=None)
    )
    await session.commit()
