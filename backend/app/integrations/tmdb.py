import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.settings import BASE_DIR

logger = logging.getLogger(__name__)

TMDBDiscoverSort = Literal["popularity_desc", "release_date_asc", "release_date_desc"]
TMDB_MAX_PAGE = 500


class TMDBSettings(BaseSettings):
    tmdb_access_token: SecretStr = SecretStr("")
    tmdb_base_url: HttpUrl = HttpUrl("https://api.themoviedb.org/3/")
    tmdb_timeout_seconds: float = Field(default=10, gt=0, le=60)
    tmdb_language: str = Field(default="ru-RU", pattern=r"^[a-z]{2}-[A-Z]{2}$")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("tmdb_base_url")
    @classmethod
    def validate_base_url(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.scheme != "https"
            or value.username
            or value.password
            or value.query
            or value.fragment
        ):
            raise ValueError("TMDB_BASE_URL must use HTTPS without credentials or query")
        return value


class TMDBMovie(BaseModel):
    tmdb_id: int = Field(validation_alias="id", gt=0)
    title: str = Field(min_length=1)
    original_title: str | None = None
    overview: str | None = None
    release_date: date | None = None
    poster_path: str | None = None
    original_language: str | None = None
    genre_ids: list[int] = Field(default_factory=list)

    @field_validator("release_date", mode="before")
    @classmethod
    def normalize_release_date(cls, value):
        return None if value == "" else value


class TMDBSearchResult(BaseModel):
    page: int = Field(ge=1)
    results: list[TMDBMovie]
    total_pages: int = Field(ge=0)
    total_results: int = Field(ge=0)


class TMDBGenre(BaseModel):
    tmdb_id: int = Field(validation_alias="id", gt=0, le=2147483647)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Genre name must not be blank")
        return value


class TMDBMovieDetails(TMDBMovie):
    tmdb_id: int = Field(validation_alias="id", gt=0, le=2147483647)
    original_language: str | None = Field(default=None, max_length=10)
    runtime: int | None = Field(default=None, gt=0, le=2147483647)
    genres: list[TMDBGenre]
    adult: bool
    vote_average: Decimal | None = Field(default=None, ge=0, le=10)
    vote_count: int | None = Field(default=None, ge=0, le=2147483647)

    @field_validator("runtime", mode="before")
    @classmethod
    def normalize_runtime(cls, value):
        return None if value == 0 else value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Movie title must not be blank")
        return value


class TMDBClient:
    def __init__(self, client: httpx.AsyncClient, language: str):
        self.client = client
        self.language = language

    async def get_movie(self, tmdb_id: int) -> TMDBMovieDetails:
        try:
            response = await self.client.get(
                f"movie/{tmdb_id}", params={"language": self.language}
            )
            if response.status_code == 404:
                raise HTTPException(404, "Фильм не найден")
            response.raise_for_status()
            movie = TMDBMovieDetails.model_validate(response.json())
            if movie.tmdb_id != tmdb_id:
                raise ValueError("Unexpected TMDB movie ID")
            if movie.adult:
                raise HTTPException(404, "Фильм не найден")
            return movie
        except httpx.HTTPStatusError as exc:
            logger.warning("TMDB details failed with HTTP %s", exc.response.status_code)
            raise HTTPException(502, "TMDB временно недоступен") from None
        except httpx.RequestError:
            logger.warning("TMDB details connection failed")
            raise HTTPException(502, "Не удалось подключиться к TMDB") from None
        except (ValidationError, ValueError):
            logger.warning("TMDB details returned invalid data")
            raise HTTPException(502, "TMDB вернул некорректные данные") from None

    async def search_movies(self, query: str, page: int = 1) -> TMDBSearchResult:
        query = query.strip()
        if not query or len(query) > 200:
            raise ValueError("Search query must contain between 1 and 200 characters")
        if not 1 <= page <= TMDB_MAX_PAGE:
            raise ValueError("Search page must be between 1 and 500")
        return await self._get_movie_page("search/movie", page, {"query": query})

    async def discover_movies(
        self,
        *,
        page: int,
        tmdb_genre_id: int | None,
        year: int | None,
        sort: TMDBDiscoverSort,
    ) -> TMDBSearchResult:
        sort_by = {
            "popularity_desc": "popularity.desc",
            "release_date_asc": "primary_release_date.asc",
            "release_date_desc": "primary_release_date.desc",
        }
        filters: dict[str, str | int] = {"sort_by": sort_by[sort]}
        if tmdb_genre_id is not None:
            filters["with_genres"] = tmdb_genre_id
        if year is not None:
            filters["primary_release_year"] = year

        result = await self._get_movie_page("discover/movie", page, filters)
        result.total_pages = min(result.total_pages, TMDB_MAX_PAGE)
        return result

    async def _get_movie_page(
        self, endpoint: str, page: int, filters: dict[str, str | int]
    ) -> TMDBSearchResult:
        try:
            response = await self.client.get(
                endpoint,
                params={
                    **filters,
                    "page": page,
                    "language": self.language,
                    "include_adult": "false",
                },
            )
            response.raise_for_status()
            return TMDBSearchResult.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "TMDB %s failed with HTTP %s", endpoint, exc.response.status_code
            )
            raise HTTPException(502, "TMDB временно недоступен") from None
        except httpx.RequestError:
            logger.warning("TMDB %s connection failed", endpoint)
            raise HTTPException(502, "Не удалось подключиться к TMDB") from None
        except (ValidationError, ValueError):
            logger.warning("TMDB %s returned invalid data", endpoint)
            raise HTTPException(502, "TMDB вернул некорректные данные") from None


@asynccontextmanager
async def open_tmdb_client(
    config: TMDBSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[TMDBClient]:
    config = config if config is not None else TMDBSettings()
    token = config.tmdb_access_token.get_secret_value().strip()
    if not token:
        raise HTTPException(503, "TMDB не настроен: укажите TMDB_ACCESS_TOKEN")
    async with httpx.AsyncClient(
        base_url=str(config.tmdb_base_url).rstrip("/") + "/",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=httpx.Timeout(config.tmdb_timeout_seconds),
        follow_redirects=False,
        transport=transport,
    ) as client:
        yield TMDBClient(client, config.tmdb_language)
