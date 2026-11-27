from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)


def validate_critic_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Текст не должен содержать нулевой символ")
    return value


CriticText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(validate_critic_text),
]
ReviewLanguage = Annotated[
    str, StringConstraints(min_length=2, max_length=2, pattern=r"^[a-z]{2}$")
]


class CriticReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movie_id: int = Field(ge=1, le=2147483647, strict=True)
    source_name: CriticText
    critic_name: CriticText | None = None
    language: ReviewLanguage
    external_url: HttpUrl
    title: CriticText | None = None
    excerpt: CriticText
    published_at: AwareDatetime | None = None

    @field_validator("external_url")
    @classmethod
    def validate_publication_url(cls, value: HttpUrl) -> HttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("Ссылка не должна содержать логин и пароль")
        return value


class CriticSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    website_url: str | None


class CriticAuthorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CriticReviewResponse(BaseModel):
    id: int
    movie_id: int
    source: CriticSourceResponse
    critic: CriticAuthorResponse | None
    language: str
    external_url: str
    title: str | None
    excerpt: str
    published_at: datetime | None


class CriticReviewPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[CriticReviewResponse]


class CriticReviewImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    movie_ids: list[Annotated[int, Field(strict=True, ge=1, le=2147483647)]] = Field(
        min_length=1, max_length=5
    )

    @field_validator("movie_ids")
    @classmethod
    def validate_unique_movies(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("ID фильмов не должны повторяться")
        return value


class CriticReviewImportResult(BaseModel):
    movie_id: int
    fetched: int = 0
    imported: int = 0
    skipped_existing: int = 0
    skipped_unmatched: int = 0


class CriticReviewImportResponse(BaseModel):
    source: str = "nyt"
    imported: int
    results: list[CriticReviewImportResult]
