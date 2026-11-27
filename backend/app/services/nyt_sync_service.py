import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import async_session
from app.db.models import ExternalSyncState, Movie
from app.integrations.nyt import (
    NYTArticle,
    article_film_tags,
    article_matches_movie,
    normalize_film_title,
    open_nyt_client,
)
from app.repositories.critic_review_repository import (
    InactiveCriticSourceError,
    get_or_create_nyt_source,
    save_nyt_review,
)
from app.repositories.sync_state_repository import (
    NYT_SYNC_NAME,
    acquire_nyt_sync_lease,
    release_nyt_sync_lease,
    renew_nyt_sync_lease,
)

logger = logging.getLogger(__name__)


async def sync_new_nyt_reviews() -> int:
    token = uuid4()
    async with async_session() as session:
        if not await acquire_nyt_sync_lease(session, token):
            return 0
        imported = 0
        try:
            state = await session.get(ExternalSyncState, NYT_SYNC_NAME)
            yesterday = datetime.now(UTC).date() - timedelta(days=1)
            if state.last_synced_date and state.last_synced_date >= yesterday:
                return 0
            if state.initial_sync_date is None:
                state.initial_sync_date = yesterday - timedelta(days=1)
                await session.commit()
            day = state.last_synced_date or state.initial_sync_date
            end_day = min(yesterday, day + timedelta(days=30))
            movies = (
                await session.execute(
                    select(
                        Movie.id, Movie.title, Movie.original_title, Movie.release_date
                    )
                    .where(Movie.release_date.is_not(None))
                    .order_by(Movie.id)
                )
            ).all()
            movie_index: dict[str, dict] = {}
            for movie in movies:
                for title in (movie.title, movie.original_title):
                    if title:
                        movie_index.setdefault(normalize_film_title(title), {})[
                            movie.id
                        ] = movie
            await session.rollback()
            async with open_nyt_client() as client:
                while day <= end_day:
                    for page in range(100):
                        await renew_nyt_sync_lease(session, token)
                        await session.commit()
                        documents, total = await client.get_publications(day, page)
                        candidates = []
                        for document in documents:
                            try:
                                article = NYTArticle.model_validate(document)
                            except ValidationError:
                                continue
                            if article.pub_date.astimezone(UTC).date() != day:
                                raise HTTPException(
                                    502, "NYT вернул статью за другой день"
                                )
                            films = article_film_tags(article)
                            if len(films) != 1:
                                continue
                            title, _ = next(iter(films))
                            matches = [
                                movie
                                for movie in movie_index.get(title, {}).values()
                                if article_matches_movie(
                                    article, {title}, movie.release_date.year
                                )
                            ]
                            if len(matches) == 1:
                                candidates.append((matches[0], article))
                        state = await renew_nyt_sync_lease(session, token)
                        for movie, article in sorted(
                            candidates, key=lambda candidate: candidate[0].id
                        ):
                            current = (
                                await session.execute(
                                    select(
                                        Movie.id,
                                        Movie.title,
                                        Movie.original_title,
                                        Movie.release_date,
                                    )
                                    .where(Movie.id == movie.id)
                                    .with_for_update(read=True)
                                )
                            ).one_or_none()
                            if current != movie:
                                raise HTTPException(409, "Данные фильма изменились")
                        source = await get_or_create_nyt_source(session)
                        for movie, article in candidates:
                            imported += await save_nyt_review(
                                session, movie.id, source, article
                            )
                        complete = (page + 1) * 10 >= total
                        if complete and (
                            state.last_synced_date is None
                            or day > state.last_synced_date
                        ):
                            state.last_synced_date = day
                        await session.commit()
                        if complete:
                            break
                    day += timedelta(days=1)
            return imported
        finally:
            await session.rollback()
            await release_nyt_sync_lease(session, token)


async def run_nyt_daily_sync() -> None:
    try:
        imported = await sync_new_nyt_reviews()
        logger.info("NYT daily sync completed: imported=%s", imported)
    except (
        HTTPException,
        InactiveCriticSourceError,
        SQLAlchemyError,
        OSError,
        RuntimeError,
        TimeoutError,
    ) as exc:
        logger.error(
            "NYT daily sync failed (%s); progress retained", type(exc).__name__
        )
