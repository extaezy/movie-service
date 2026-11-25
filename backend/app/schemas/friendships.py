from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

FriendshipStatus = Literal["pending", "accepted", "rejected"]
FriendshipDecision = Literal["accepted", "rejected"]


class FriendshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_low_id: UUID
    user_high_id: UUID
    requested_by_id: UUID
    status: FriendshipStatus
    created_at: datetime
    updated_at: datetime


class FriendUserResponse(BaseModel):
    id: UUID
    username: str
    avatar_url: str | None


class IncomingFriendRequest(BaseModel):
    id: int
    sender: FriendUserResponse
    created_at: datetime


class FriendRequestPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[IncomingFriendRequest]


class FriendPage(BaseModel):
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[FriendUserResponse]
