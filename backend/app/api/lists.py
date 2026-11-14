from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_optional_current_user
from app.db.database import get_db
from app.db.models import Movie, User
from app.repositories.list_repository import (
    add_movie_to_list,
    get_visible_movie_list,
    remove_movie_from_list,
)
from app.schemas.lists import (
    ListType,
    MovieListAdd,
    MovieListEntryResponse,
    MovieListPage,
)

router = APIRouter(tags=["lists"])
MovieId = Annotated[int, Path(ge=1, le=2147483647)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/movies/{movie_id}/lists",
    status_code=201,
    responses={200: {"model": MovieListEntryResponse}},
)
async def post_movie_list_entry(
    movie_id: MovieId,
    entry: MovieListAdd,
    user: CurrentUser,
    session: DatabaseSession,
    response: Response,
) -> MovieListEntryResponse:
    if (
        await session.get(
            Movie, movie_id, with_for_update={"read": True, "key_share": True}
        )
        is None
    ):
        raise HTTPException(404, "Фильм не найден")
    created = await add_movie_to_list(session, user.id, movie_id, entry.list_type)
    await session.commit()
    if not created:
        response.status_code = 200
    return MovieListEntryResponse(movie_id=movie_id, list_type=entry.list_type)


@router.delete("/movies/{movie_id}/lists/{list_type}", status_code=204)
async def delete_movie_list_entry(
    movie_id: MovieId, list_type: ListType, user: CurrentUser, session: DatabaseSession
) -> Response:
    if await session.get(Movie, movie_id) is None:
        raise HTTPException(404, "Фильм не найден")
    await remove_movie_from_list(session, user.id, movie_id, list_type)
    await session.commit()
    return Response(status_code=204)


@router.get(
    "/users/{username}/movies", openapi_extra={"security": [{}, {"HTTPBearer": []}]}
)
async def get_user_movie_list(
    username: Annotated[str, Path(min_length=4, max_length=20)],
    list_type: ListType,
    viewer: Annotated[User | None, Depends(get_optional_current_user)],
    session: DatabaseSession,
    response: Response,
    page: Annotated[int, Query(ge=1, le=2147483647)] = 1,
) -> MovieListPage:
    movie_page = await get_visible_movie_list(
        session,
        username,
        list_type,
        viewer.id if viewer is not None else None,
        page=page,
    )
    if movie_page is None:
        raise HTTPException(
            404, "Список не найден", headers={"Cache-Control": "no-store"}
        )
    response.headers["Cache-Control"] = "no-store"
    return movie_page
