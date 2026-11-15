from pydantic import BaseModel, ConfigDict, Field


class RatingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(strict=True, ge=1, le=10)


class RatingResponse(BaseModel):
    movie_id: int
    score: int
