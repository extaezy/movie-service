from uuid import UUID

from sqlalchemy import delete, func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Movie, MovieGenre, Profile, User, UserMovieEntry
from app.repositories.profile_repository import profile_access_condition
from app.schemas.lists import ListedMovieResponse, ListType, MovieListPage

MOVIE_LIST_PAGE_SIZE = 20


async def add_movie_to_list(
    session: AsyncSession, user_id: UUID, movie_id: int, list_type: ListType
) -> bool:
    statement = (
        insert(UserMovieEntry)
        .values(user_id=user_id, movie_id=movie_id, list_type=list_type)
        .on_conflict_do_nothing(
            index_elements=[
                UserMovieEntry.user_id,
                UserMovieEntry.movie_id,
                UserMovieEntry.list_type,
            ]
        )
        .returning(UserMovieEntry.movie_id)
    )
    return await session.scalar(statement) is not None


async def remove_movie_from_list(
    session: AsyncSession, user_id: UUID, movie_id: int, list_type: ListType
) -> None:
    await session.execute(
        delete(UserMovieEntry).where(
            UserMovieEntry.user_id == user_id,
            UserMovieEntry.movie_id == movie_id,
            UserMovieEntry.list_type == list_type,
        )
    )


async def get_visible_movie_list(
    session: AsyncSession,
    username: str,
    list_type: ListType,
    viewer_id: UUID | None,
    *,
    page: int,
    q: str | None = None,
    genre_id: int | None = None,
) -> MovieListPage | None:
    list_filters = [
        UserMovieEntry.user_id == User.id,
        UserMovieEntry.list_type == list_type,
    ]
    if q:
        list_filters.append(Movie.title.icontains(q, autoescape=True))
    if genre_id is not None:
        list_filters.append(
            select(MovieGenre.movie_id)
            .where(MovieGenre.movie_id == Movie.id, MovieGenre.genre_id == genre_id)
            .exists()
        )

    matching_movies = (
        select(
            Movie.id,
            Movie.tmdb_id,
            Movie.title,
            Movie.poster_path,
            Movie.release_date,
            UserMovieEntry.created_at.label("added_at"),
        )
        .select_from(UserMovieEntry)
        .join(Movie, Movie.id == UserMovieEntry.movie_id)
        .where(*list_filters)
        .correlate(User)
    )
    total_results = matching_movies.with_only_columns(func.count()).scalar_subquery()
    page_movies = (
        matching_movies.order_by(UserMovieEntry.created_at.desc(), Movie.id.desc())
        .offset((page - 1) * MOVIE_LIST_PAGE_SIZE)
        .limit(MOVIE_LIST_PAGE_SIZE)
        .lateral()
    )
    statement = (
        select(page_movies, total_results.label("total_results"))
        .select_from(User)
        .outerjoin(Profile, Profile.user_id == User.id)
        .outerjoin(page_movies, true())
        .where(User.username == username, profile_access_condition(viewer_id))
        .order_by(page_movies.c.added_at.desc(), page_movies.c.id.desc())
    )
    rows = (await session.execute(statement)).mappings().all()
    if not rows:
        return None
    count = rows[0]["total_results"]
    return MovieListPage(
        page=page,
        page_size=MOVIE_LIST_PAGE_SIZE,
        total_results=count,
        total_pages=(count + MOVIE_LIST_PAGE_SIZE - 1) // MOVIE_LIST_PAGE_SIZE,
        results=[
            ListedMovieResponse.model_validate(row)
            for row in rows
            if row["id"] is not None
        ],
    )
