from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProfileSummary(BaseModel):
    id: UUID
    platform: str
    username: str | None
    display_name: str | None

    model_config = {"from_attributes": True}


class ProfileLinkOut(BaseModel):
    id: UUID
    source_profile: ProfileSummary
    target_profile: ProfileSummary
    confidence: float
    match_method: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileLinkListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProfileLinkOut]


class ReviewAction(BaseModel):
    action: str  # "confirm" | "reject"
