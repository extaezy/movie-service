from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MovieSort = Literal["release_date_asc", "release_date_desc"]


class GenreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int
    name: str


class MovieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tmdb_id: int
    title: str
    original_title: str | None
    overview: str | None
    release_date: date | None
    poster_path: str | None
    runtime: int | None
    original_language: str | None
    genres: list[GenreResponse] = Field(default_factory=list)


class MovieDetailResponse(MovieResponse):
    average_rating: float | None
    ratings_count: int
    tmdb_vote_average: float | None
    tmdb_vote_count: int | None
    tmdb_rating_updated_at: datetime | None


class MoviePage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[MovieResponse]
