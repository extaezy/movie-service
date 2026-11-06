from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.settings import DatabaseSettings, connection_options

database_settings = DatabaseSettings()
database_url, connect_args = connection_options(database_settings)


engine = create_async_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=database_settings.database_pool_size,
    max_overflow=database_settings.database_max_overflow,
    pool_timeout=10,
    hide_parameters=True,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except (DBAPIError, SQLAlchemyTimeoutError, OSError, TimeoutError) as exc:
            await session.rollback()
            raise HTTPException(
                status_code=503, detail="База данных временно недоступна"
            ) from exc
