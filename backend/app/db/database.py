from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.core.config import settings


engine = create_async_engine(
    settings.database_url,
    connect_args={"ssl": "require"},
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session