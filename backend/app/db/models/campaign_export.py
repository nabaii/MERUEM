import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.campaign import Campaign


class ExportFormat(str, enum.Enum):
    meta = "meta"
    twitter = "twitter"
    csv = "csv"


class ExportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class CampaignExport(Base):
    __tablename__ = "campaign_exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format_enum"), nullable=False
    )
    profile_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status_enum"), default=ExportStatus.pending
    )
    file_key: Mapped[Optional[str]] = mapped_column(String(500))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="exports")
