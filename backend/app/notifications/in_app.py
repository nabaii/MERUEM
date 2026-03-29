"""
In-app notification helpers — write Notification rows to the database.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.notification import Notification, NotificationType


def create_notification(
    db: Session,
    account_id: uuid.UUID,
    type: NotificationType,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> Notification:
    notif = Notification(
        account_id=account_id,
        type=type,
        title=title,
        body=body,
        data=data or {},
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def notify_export_ready(
    db: Session,
    account_id: uuid.UUID,
    campaign_name: str,
    export_id: uuid.UUID,
) -> Notification:
    return create_notification(
        db,
        account_id=account_id,
        type=NotificationType.export_ready,
        title="Export ready",
        body=f"Your audience export for '{campaign_name}' is ready to download.",
        data={"export_id": str(export_id)},
    )


def notify_export_failed(
    db: Session,
    account_id: uuid.UUID,
    campaign_name: str,
    error: str,
) -> Notification:
    return create_notification(
        db,
        account_id=account_id,
        type=NotificationType.export_failed,
        title="Export failed",
        body=f"Export for '{campaign_name}' failed: {error}",
        data={"error": error},
    )


def notify_campaign_activated(
    db: Session,
    account_id: uuid.UUID,
    campaign_name: str,
    campaign_id: uuid.UUID,
) -> Notification:
    return create_notification(
        db,
        account_id=account_id,
        type=NotificationType.campaign_activated,
        title="Campaign activated",
        body=f"Campaign '{campaign_name}' is now active.",
        data={"campaign_id": str(campaign_id)},
    )
