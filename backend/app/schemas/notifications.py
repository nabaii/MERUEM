from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.db.models.notification import NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    is_read: bool
    data: Optional[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
