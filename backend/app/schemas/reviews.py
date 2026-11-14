from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def validate_review_text(text: str) -> str:
    if not text.strip():
        raise ValueError("Текст рецензии не должен быть пустым")
    if "\x00" in text:
        raise ValueError("Текст рецензии не должен содержать нулевой символ")
    return text


ReviewText = Annotated[str, Field(min_length=1), AfterValidator(validate_review_text)]


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: ReviewText
    contains_spoilers: bool = Field(default=False, strict=True)


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: ReviewText | None = None
    contains_spoilers: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def validate_changes(self) -> "ReviewUpdate":
        if not self.model_fields_set:
            raise ValueError("Укажите текст или признак спойлеров")
        if None in self.model_dump(exclude_unset=True).values():
            raise ValueError("Поля рецензии не могут быть null")
        return self


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: int
    text: str
    contains_spoilers: bool
    created_at: datetime


class ReviewUpdateResponse(ReviewResponse):
    updated_at: datetime
