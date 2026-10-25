import asyncio
from sqlalchemy import text
from app.db.database import engine


async def main():
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Подключение успешно:", result.scalar())
    except Exception as e:
        print(f"Ошибка: {type(e).__name__}: {e}")
    finally:
        await engine.dispose()


asyncio.run(main())