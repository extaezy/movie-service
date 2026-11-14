from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ListType = Literal["watchlist", "watched", "favorite"]


class MovieListAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    list_type: ListType


class MovieListEntryResponse(BaseModel):
    movie_id: int
    list_type: ListType


class ListedMovieResponse(BaseModel):
    id: int
    tmdb_id: int
    title: str
    poster_path: str | None
    release_date: date | None
    added_at: datetime


class MovieListPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[ListedMovieResponse]
