import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.integrations.nyt import NYTSettings
from app.services.nyt_sync_service import run_nyt_daily_sync


@asynccontextmanager
async def open_nyt_scheduler() -> AsyncIterator[None]:
    config = NYTSettings()
    if not config.nyt_sync_enabled or not config.nyt_api_key.get_secret_value().strip():
        yield
        return
    tasks = set()

    async def run_job() -> None:
        task = asyncio.current_task()
        tasks.add(task)
        try:
            await run_nyt_daily_sync()
        except asyncio.CancelledError:
            return
        finally:
            tasks.discard(task)

    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        run_job,
        "cron",
        hour=config.nyt_sync_hour_utc,
        minute=0,
        id="nyt_daily_reviews",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        next_run_time=datetime.now(UTC),
    )
    scheduler.start()
    try:
        yield
    finally:
        scheduler.pause()
        await asyncio.sleep(0)
        pending = list(tasks)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        scheduler.shutdown(wait=False)
        await asyncio.sleep(0)
