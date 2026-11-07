import asyncio
import sys

from fastapi import HTTPException
from pydantic import ValidationError

from app.integrations.tmdb import open_tmdb_client


async def check_tmdb() -> int:
    try:
        async with open_tmdb_client() as client:
            result = await client.search_movies("The Matrix")
        print(f"TMDB connection: OK; search results: {result.total_results}")
        return 0
    except HTTPException as exc:
        print(f"TMDB check failed ({exc.status_code}): {exc.detail}")
        return 1
    except ValidationError:
        print("TMDB check failed: invalid TMDB settings in environment or backend/.env")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(check_tmdb()))
