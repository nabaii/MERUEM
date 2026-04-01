from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CollectionJobCreate(BaseModel):
    platform: str = Field(
        default="twitter",
        pattern="^(twitter|instagram|facebook|tiktok|linkedin|manual)$",
    )
    params: dict[str, Any] | None = None
    # params examples:
    # {"seed_usernames": ["BudweiserNG", "GTBankNG"], "max_profiles": 1000}
    # {"search_query": "#Lagos tech", "max_profiles": 500}


class CollectionJobOut(BaseModel):
    id: UUID
    platform: str
    status: str
    params: dict[str, Any] | None
    celery_task_id: str | None
    profiles_collected: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
