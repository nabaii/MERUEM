from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClusterOut(BaseModel):
    id: int
    label: str | None
    description: str | None
    member_count: int
    top_interests: dict | None
    last_updated: datetime

    model_config = {"from_attributes": True}


class ClusterListResponse(BaseModel):
    total: int
    items: list[ClusterOut]


class ClusterProfileOut(BaseModel):
    id: UUID
    platform: str
    username: str | None
    display_name: str | None
    follower_count: int | None
    location_inferred: str | None
    affinity_score: float | None

    model_config = {"from_attributes": True}


class ClusterProfilesResponse(BaseModel):
    cluster_id: int
    total: int
    limit: int
    offset: int
    items: list[ClusterProfileOut]
