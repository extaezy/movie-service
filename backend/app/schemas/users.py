from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


def validate_profile_text(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Поле профиля не должно содержать нулевой символ")
    return value


DisplayName = Annotated[
    str, Field(max_length=100), AfterValidator(validate_profile_text)
]
ProfileBio = Annotated[
    str, Field(max_length=1000), AfterValidator(validate_profile_text)
]


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    bio: ProfileBio | None = None
    avatar_url: HttpUrl | None = None
    is_private: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def validate_changes(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("Укажите хотя бы одно поле профиля")
        if "is_private" in self.model_fields_set and self.is_private is None:
            raise ValueError("Режим приватности не может быть null")
        return self


class PublicProfileResponse(BaseModel):
    username: str
    avatar_url: str | None


class ProfileResponse(PublicProfileResponse):
    id: UUID
    display_name: str | None
    bio: str | None
    is_private: bool


class UserRatingResponse(BaseModel):
    movie_id: int
    score: int
    created_at: datetime
    updated_at: datetime


class UserRatingPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[UserRatingResponse]
