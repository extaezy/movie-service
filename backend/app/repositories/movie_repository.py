from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Genre, Movie, MovieGenre, Rating
from app.integrations.tmdb import TMDBMovieDetails
from app.schemas.movies import (
    GenreResponse,
    MovieDetailResponse,
    MoviePage,
    MovieResponse,
    MovieSort,
)

CATALOG_PAGE_SIZE = 20


async def list_movies(
    session: AsyncSession,
    *,
    page: int,
    genre_id: int | None,
    year: int | None,
    sort: MovieSort,
) -> MoviePage:
    filters = []
    if genre_id is not None:
        filters.append(
            select(MovieGenre.movie_id)
            .where(MovieGenre.movie_id == Movie.id, MovieGenre.genre_id == genre_id)
            .exists()
        )
    if year is not None:
        filters.append(Movie.release_date.between(date(year, 1, 1), date(year, 12, 31)))

    release_order = (
        Movie.release_date.asc()
        if sort == "release_date_asc"
        else Movie.release_date.desc()
    )
    offset = (page - 1) * CATALOG_PAGE_SIZE
    total_results = (
        await session.scalar(select(func.count()).select_from(Movie).where(*filters))
        or 0
    )
    result = MoviePage(
        page=page,
        page_size=CATALOG_PAGE_SIZE,
        total_results=total_results,
        total_pages=(total_results + CATALOG_PAGE_SIZE - 1) // CATALOG_PAGE_SIZE,
        results=[],
    )
    if offset >= total_results:
        return result

    movies = await session.scalars(
        select(Movie)
        .where(*filters)
        .order_by(release_order.nulls_last(), Movie.id)
        .offset(offset)
        .limit(CATALOG_PAGE_SIZE)
    )
    result.results = [MovieResponse.model_validate(movie) for movie in movies]
    movies_by_id = {movie.id: movie for movie in result.results}
    genres = await session.execute(
        select(MovieGenre.movie_id, Genre)
        .join(Genre, Genre.id == MovieGenre.genre_id)
        .where(MovieGenre.movie_id.in_(movies_by_id))
        .order_by(Genre.tmdb_id)
    )
    for movie_id, genre in genres:
        movies_by_id[movie_id].genres.append(GenreResponse.model_validate(genre))
    return result


async def movie_response(session: AsyncSession, movie: Movie) -> MovieDetailResponse:
    genres = await session.scalars(
        select(Genre)
        .join(MovieGenre, MovieGenre.genre_id == Genre.id)
        .where(MovieGenre.movie_id == movie.id)
        .order_by(Genre.tmdb_id)
    )
    ratings = await session.execute(
        select(func.round(func.avg(Rating.score), 2), func.count())
        .select_from(Rating)
        .where(Rating.movie_id == movie.id)
    )
    average_rating, ratings_count = ratings.one()
    return MovieDetailResponse(
        **MovieResponse.model_validate(movie).model_dump(exclude={"genres"}),
        genres=[GenreResponse.model_validate(genre) for genre in genres],
        average_rating=average_rating,
        ratings_count=ratings_count,
        tmdb_vote_average=movie.tmdb_vote_average,
        tmdb_vote_count=movie.tmdb_vote_count,
        tmdb_rating_updated_at=movie.tmdb_rating_updated_at,
    )


async def get_movie_by_tmdb_id(
    session: AsyncSession, tmdb_id: int
) -> MovieDetailResponse | None:
    movie = await session.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    return await movie_response(session, movie) if movie is not None else None


async def get_movie_by_id(
    session: AsyncSession, movie_id: int
) -> MovieDetailResponse | None:
    movie = await session.get(Movie, movie_id)
    return await movie_response(session, movie) if movie is not None else None


async def save_movie(
    session: AsyncSession, details: TMDBMovieDetails
) -> MovieDetailResponse:
    movie_values = details.model_dump(
        exclude={"genres", "genre_ids", "adult", "vote_average", "vote_count"}
    )
    if details.vote_count == 0 or (
        details.vote_count is not None and details.vote_average is not None
    ):
        movie_values.update(
            tmdb_vote_average=details.vote_average if details.vote_count else None,
            tmdb_vote_count=details.vote_count,
            tmdb_rating_updated_at=func.now(),
        )
    movie_id = await session.scalar(
        insert(Movie)
        .values(**movie_values)
        .on_conflict_do_nothing(index_elements=[Movie.tmdb_id])
        .returning(Movie.id)
    )
    if movie_id is not None:
        unique_genres = {genre.tmdb_id: genre for genre in details.genres}
        for tmdb_id, genre in sorted(unique_genres.items()):
            genre_id = await session.scalar(
                insert(Genre)
                .values(tmdb_id=tmdb_id, name=genre.name)
                .on_conflict_do_nothing(index_elements=[Genre.tmdb_id])
                .returning(Genre.id)
            )
            if genre_id is None:
                genre_id = await session.scalar(
                    select(Genre.id).where(Genre.tmdb_id == tmdb_id)
                )
            await session.execute(
                insert(MovieGenre)
                .values(movie_id=movie_id, genre_id=genre_id)
                .on_conflict_do_nothing()
            )
    result = await get_movie_by_tmdb_id(session, details.tmdb_id)
    if result is None:
        raise RuntimeError("Movie missing after insert")
    return result
