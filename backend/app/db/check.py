import asyncio
import sys

from asyncpg import PostgresError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import engine


async def check_database() -> int:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            print("PostgreSQL connection: OK")
            version_table = await connection.scalar(
                text("SELECT to_regclass('movie_service.alembic_version')")
            )
            if version_table is None:
                print("Migration not applied. Run: python -m alembic upgrade head")
                return 1
            revision = await connection.scalar(
                text("SELECT version_num FROM movie_service.alembic_version")
            )
            print(f"Migration revision: {revision or 'base'}")
            tables = await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'movie_service' AND table_type = 'BASE TABLE' "
                    "AND table_name <> 'alembic_version'"
                )
            )
            print(f"Application tables: {tables}")
            return 0 if revision and tables >= 12 else 1
    except (SQLAlchemyError, PostgresError, OSError, TimeoutError, ValueError) as exc:
        print(
            f"Database check failed ({type(exc).__name__}). Check connection settings and network."
        )
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(check_database()))
