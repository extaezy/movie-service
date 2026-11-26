import asyncio
from random import sample, shuffle

from app.integrations.tmdb import TMDBClient, TMDBRecommendedMovie
from app.schemas.movies import SimilarMoviesResponse

SIMILAR_MOVIE_LIMIT = 15
RECOMMENDATION_POOL_LIMIT = 150
RECOMMENDATION_PAGE_LIMIT = 8
PRIMARY_POOL_LIMIT = 20
PRIMARY_SAMPLE_SIZE = 3
SECONDARY_SAMPLE_SIZE = 12


async def get_similar_movies(client: TMDBClient, tmdb_id: int) -> SimilarMoviesResponse:
    first_page = await client.get_recommendations(tmdb_id)
    pages = [first_page]
    concurrency = asyncio.Semaphore(3)

    async def fetch_page(page: int):
        async with concurrency:
            return await client.get_recommendations(tmdb_id, page)

    page_count = min(first_page.total_pages, RECOMMENDATION_PAGE_LIMIT)
    if page_count > 1:
        remaining_pages = await asyncio.gather(
            *(fetch_page(page) for page in range(2, page_count + 1)),
            return_exceptions=True,
        )
        for page in remaining_pages:
            if isinstance(page, BaseException):
                raise page
            pages.append(page)

    ranked_movies = [movie for page in pages for movie in page.results][
        :RECOMMENDATION_POOL_LIMIT
    ]
    primary_pool: list[TMDBRecommendedMovie] = []
    secondary_pool: list[TMDBRecommendedMovie] = []
    seen_ids = {tmdb_id}
    for position, movie in enumerate(ranked_movies, start=1):
        if movie.adult or movie.tmdb_id in seen_ids:
            continue
        seen_ids.add(movie.tmdb_id)
        if position <= PRIMARY_POOL_LIMIT:
            primary_pool.append(movie)
        else:
            secondary_pool.append(movie)

    selected = sample(primary_pool, min(PRIMARY_SAMPLE_SIZE, len(primary_pool)))
    selected.extend(
        sample(secondary_pool, min(SECONDARY_SAMPLE_SIZE, len(secondary_pool)))
    )
    missing_count = SIMILAR_MOVIE_LIMIT - len(selected)
    if missing_count > 0:
        selected_ids = {movie.tmdb_id for movie in selected}
        remaining = [
            movie
            for movie in primary_pool + secondary_pool
            if movie.tmdb_id not in selected_ids
        ]
        selected.extend(sample(remaining, min(missing_count, len(remaining))))
    shuffle(selected)
    return SimilarMoviesResponse(results=selected)
