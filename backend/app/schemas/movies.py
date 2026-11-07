from datetime import date

from pydantic import BaseModel, ConfigDict, Field


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
