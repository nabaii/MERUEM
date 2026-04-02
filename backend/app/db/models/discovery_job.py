"""Tracks Twitter/X user discovery runs."""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscoveryStatus(str, enum.Enum):
    pending = "pending"
    expanding = "expanding"      # LLM keyword expansion in progress
    searching = "searching"      # Twitter search in progress
    completed = "completed"
    failed = "failed"


class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="twitter")
    seed_keywords: Mapped[list] = mapped_column(JSONB, nullable=False)
    expanded_keywords: Mapped[Optional[list]] = mapped_column(JSONB)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    date_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[DiscoveryStatus] = mapped_column(
        Enum(DiscoveryStatus, name="discovery_status_enum"),
        default=DiscoveryStatus.pending,
    )
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    tweets_scanned: Mapped[int] = mapped_column(Integer, default=0)
    location_matched: Mapped[int] = mapped_column(Integer, default=0)
    results_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(String(2000))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
