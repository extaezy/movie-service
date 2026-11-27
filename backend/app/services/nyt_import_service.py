from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Movie
from app.integrations.nyt import (
    NYTArticle,
    article_matches_movie,
    normalize_film_title,
    open_nyt_client,
)
from app.repositories.critic_review_repository import (
    InactiveCriticSourceError,
    get_or_create_nyt_source,
    save_nyt_review,
)
from app.schemas.critic_reviews import (
    CriticReviewImportResponse,
    CriticReviewImportResult,
)


async def import_nyt_reviews(
    session: AsyncSession, movie_ids: list[int]
) -> CriticReviewImportResponse:
    rows = (
        await session.execute(
            select(Movie.id, Movie.title, Movie.original_title, Movie.release_date)
            .where(Movie.id.in_(movie_ids))
            .order_by(Movie.id)
        )
    ).all()
    if len(rows) != len(movie_ids):
        raise HTTPException(404, "Фильм не найден")
    movies = {row.id: row for row in rows}
    await session.rollback()
    results = []
    candidates: dict[int, list[NYTArticle]] = {}
    async with open_nyt_client() as client:
        for movie_id in movie_ids:
            movie = movies[movie_id]
            result = CriticReviewImportResult(movie_id=movie_id)
            results.append(result)
            if movie.release_date is None:
                continue
            documents = await client.search_reviews(movie.original_title or movie.title)
            result.fetched = len(documents)
            titles = {
                normalize_film_title(title)
                for title in (movie.title, movie.original_title)
                if title
            }
            candidates[movie_id] = []
            for document in documents:
                try:
                    article = NYTArticle.model_validate(document)
                except ValidationError:
                    result.skipped_unmatched += 1
                    continue
                if article_matches_movie(article, titles, movie.release_date.year):
                    candidates[movie_id].append(article)
                else:
                    result.skipped_unmatched += 1
    if not any(candidates.values()):
        return CriticReviewImportResponse(imported=0, results=results)
    try:
        current_rows = (
            await session.execute(
                select(Movie.id, Movie.title, Movie.original_title, Movie.release_date)
                .where(Movie.id.in_(movie_ids))
                .order_by(Movie.id)
                .with_for_update(read=True)
            )
        ).all()
        if current_rows != rows:
            raise HTTPException(409, "Данные фильма изменились. Повторите импорт")
        source = await get_or_create_nyt_source(session)
        for result in results:
            for article in candidates.get(result.movie_id, []):
                if await save_nyt_review(session, result.movie_id, source, article):
                    result.imported += 1
                else:
                    result.skipped_existing += 1
        await session.commit()
    except InactiveCriticSourceError as exc:
        await session.rollback()
        raise HTTPException(409, str(exc)) from exc
    except Exception:
        await session.rollback()
        raise
    return CriticReviewImportResponse(
        imported=sum(result.imported for result in results), results=results
    )
