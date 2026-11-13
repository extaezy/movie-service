from uuid import UUID

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Rating


async def upsert_rating(
    session: AsyncSession, user_id: UUID, movie_id: int, score: int
) -> None:
    statement = insert(Rating).values(user_id=user_id, movie_id=movie_id, score=score)
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[Rating.user_id, Rating.movie_id],
            set_={"score": statement.excluded.score, "updated_at": func.now()},
        )
    )


async def delete_rating(session: AsyncSession, user_id: UUID, movie_id: int) -> None:
    await session.execute(
        delete(Rating).where(Rating.user_id == user_id, Rating.movie_id == movie_id)
    )
