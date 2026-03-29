from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentAccount, DbDep
from app.db.models.notification import Notification
from app.schemas.notifications import NotificationListResponse, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    db: DbDep,
    current: CurrentAccount,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Notification).filter(Notification.account_id == current.id)
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712

    total = q.count()
    unread_count = (
        db.query(Notification)
        .filter(Notification.account_id == current.id, Notification.is_read == False)  # noqa: E712
        .count()
    )
    items = q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read", status_code=204)
def mark_read(notification_id: uuid.UUID, db: DbDep, current: CurrentAccount):
    notif = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.account_id == current.id,
    ).first()
    if notif:
        notif.is_read = True
        db.commit()
    return Response(status_code=204)


@router.post("/read-all", status_code=204)
def mark_all_read(db: DbDep, current: CurrentAccount):
    db.query(Notification).filter(
        Notification.account_id == current.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return Response(status_code=204)
