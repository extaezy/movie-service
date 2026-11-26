from datetime import datetime
from decimal import Decimal
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
    model_validator,
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
CriticScore = Annotated[
    Decimal, Field(ge=0, max_digits=12, decimal_places=4, allow_inf_nan=False)
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
    verdict: CriticText
    original_score: CriticScore | None = None
    score_scale: CriticScore | None = None
    published_at: AwareDatetime | None = None

    @field_validator("external_url")
    @classmethod
    def validate_publication_url(cls, value: HttpUrl) -> HttpUrl:
        if value.username is not None or value.password is not None:
            raise ValueError("Ссылка не должна содержать логин и пароль")
        return value

    @model_validator(mode="after")
    def validate_score(self) -> "CriticReviewCreate":
        if (self.original_score is None) != (self.score_scale is None):
            raise ValueError("Укажите оценку и максимум шкалы вместе")
        if self.score_scale is not None:
            if self.score_scale <= 0:
                raise ValueError("Максимум шкалы должен быть больше нуля")
            if self.original_score > self.score_scale:
                raise ValueError("Оценка не должна превышать максимум шкалы")
        return self


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
    verdict: str
    original_score: float | None
    score_scale: float | None
    normalized_score: float | None
    published_at: datetime | None


class CriticReviewPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[CriticReviewResponse]
