from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Genre, Movie, MovieGenre
from app.integrations.tmdb import TMDBMovieDetails
from app.schemas.movies import GenreResponse, MovieResponse


async def movie_response(session: AsyncSession, movie: Movie) -> MovieResponse:
    genres = await session.scalars(
        select(Genre)
        .join(MovieGenre, MovieGenre.genre_id == Genre.id)
        .where(MovieGenre.movie_id == movie.id)
        .order_by(Genre.tmdb_id)
    )
    result = MovieResponse.model_validate(movie)
    result.genres = [GenreResponse.model_validate(genre) for genre in genres]
    return result


async def get_movie_by_tmdb_id(
    session: AsyncSession, tmdb_id: int
) -> MovieResponse | None:
    movie = await session.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))
    return await movie_response(session, movie) if movie is not None else None


async def get_movie_by_id(session: AsyncSession, movie_id: int) -> MovieResponse | None:
    movie = await session.get(Movie, movie_id)
    return await movie_response(session, movie) if movie is not None else None


async def save_movie(session: AsyncSession, details: TMDBMovieDetails) -> MovieResponse:
    movie_id = await session.scalar(
        insert(Movie)
        .values(**details.model_dump(exclude={"genres", "genre_ids", "adult"}))
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
