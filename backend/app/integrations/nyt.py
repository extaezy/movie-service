import asyncio
import re
import time
import unicodedata
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

import httpx
from fastapi import HTTPException
from pydantic import (
    AwareDatetime,
    BaseModel,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.settings import BASE_DIR
from app.schemas.critic_reviews import CriticText

request_lock = asyncio.Lock()
next_request_at = 0.0


class NYTSettings(BaseSettings):
    nyt_api_key: SecretStr = SecretStr("")
    nyt_timeout_seconds: float = Field(default=15, gt=0, le=60)
    nyt_sync_enabled: bool = True
    nyt_sync_hour_utc: int = Field(default=4, ge=0, le=23)

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


class NYTKeyword(BaseModel):
    name: str
    value: str


class NYTHeadline(BaseModel):
    main: CriticText


class NYTByline(BaseModel):
    original: CriticText | None = None


class NYTArticle(BaseModel):
    external_id: CriticText = Field(validation_alias="_id")
    web_url: HttpUrl
    headline: NYTHeadline
    byline: NYTByline | None = None
    abstract: CriticText | None = None
    snippet: CriticText | None = None
    pub_date: AwareDatetime
    section_name: str
    type_of_material: str
    keywords: list[NYTKeyword] = Field(default_factory=list)

    @property
    def excerpt(self) -> str | None:
        return self.abstract or self.snippet

    @property
    def critic_name(self) -> str | None:
        name = self.byline.original if self.byline else None
        if name:
            return re.sub(r"^By\s+", "", name, flags=re.IGNORECASE).strip() or None
        return None


def normalize_film_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in value if character.isalnum())


def article_film_tags(article: NYTArticle) -> set[tuple[str, str | None]]:
    films = set()
    for keyword in article.keywords:
        if keyword.name.casefold() not in {"title", "creative_works"}:
            continue
        match = re.fullmatch(
            r"(.+?)(?:\s+\((\d{4})\))?\s+\(Movie\)", keyword.value, re.IGNORECASE
        )
        if match:
            films.add((normalize_film_title(match[1]), match[2]))
    return films


def article_matches_movie(article: NYTArticle, titles: set[str], year: int) -> bool:
    if (
        article.type_of_material.casefold() != "review"
        or article.section_name.casefold() != "movies"
        or not article.excerpt
        or article.web_url.scheme != "https"
        or article.web_url.host not in {"nytimes.com", "www.nytimes.com"}
        or article.web_url.username
        or article.web_url.password
    ):
        return False
    films = list(article_film_tags(article))
    return (
        len(set(films)) == 1
        and films[0][0] in titles
        and (films[0][1] is None or int(films[0][1]) == year)
    )


class NYTClient:
    def __init__(self, client: httpx.AsyncClient, key: str):
        self.client = client
        self.key = key

    async def search_reviews(self, title: str) -> list[dict]:
        result = await self.request_articles(
            {"q": f"{title} review", "sort": "relevance", "page": 0}
        )
        return result["docs"] or []

    async def get_publications(self, day: date, page: int) -> tuple[list[dict], int]:
        if not 0 <= page < 100:
            raise HTTPException(502, "Превышен предел страниц NYT за день")
        result = await self.request_articles(
            {
                "begin_date": day.strftime("%Y%m%d"),
                "end_date": day.strftime("%Y%m%d"),
                "sort": "oldest",
                "page": page,
            }
        )
        metadata = result.get("metadata") or result.get("meta")
        if not isinstance(metadata, dict):
            raise HTTPException(502, "NYT вернул некорректные счётчики")
        hits = metadata.get("hits")
        if type(hits) is not int or hits < 0 or hits > 1000:
            raise HTTPException(
                502, "Некорректный или слишком большой объём публикаций NYT"
            )
        documents = result["docs"] or []
        expected = min(10, max(0, hits - page * 10))
        if len(documents) != expected:
            raise HTTPException(502, "NYT вернул неполную страницу публикаций")
        return documents, hits

    async def request_articles(self, params: dict) -> dict:
        global next_request_at
        async with request_lock:
            await asyncio.sleep(max(0, next_request_at - time.monotonic()))
            next_request_at = time.monotonic() + 12
            try:
                response = await self.client.get(
                    "https://api.nytimes.com/svc/search/v2/articlesearch.json",
                    params={**params, "api-key": self.key},
                )
                if response.status_code == 429:
                    raise HTTPException(
                        502, "Лимит запросов NYT исчерпан. Повторите позже"
                    )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("status") != "OK":
                    raise ValueError
                result = payload.get("response")
                if not isinstance(result, dict) or "docs" not in result:
                    raise ValueError
                documents = result["docs"]
                if documents is not None and (
                    not isinstance(documents, list) or len(documents) > 10
                ):
                    raise ValueError
                return result
            except httpx.HTTPStatusError:
                raise HTTPException(502, "NYT отклонил запрос") from None
            except httpx.RequestError:
                raise HTTPException(502, "Не удалось подключиться к NYT") from None
            except (ValueError, ValidationError):
                raise HTTPException(502, "NYT вернул некорректные данные") from None


@asynccontextmanager
async def open_nyt_client(
    config: NYTSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[NYTClient]:
    config = config if config is not None else NYTSettings()
    key = config.nyt_api_key.get_secret_value().strip()
    if not key:
        raise HTTPException(503, "NYT не настроен: укажите NYT_API_KEY")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(config.nyt_timeout_seconds),
        follow_redirects=False,
        transport=transport,
    ) as client:
        yield NYTClient(client, key)
