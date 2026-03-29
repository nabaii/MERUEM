import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.campaign_audience import CampaignAudience
    from app.db.models.campaign_export import CampaignExport


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    exported = "exported"
    completed = "completed"


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), index=True
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status_enum"), default=CampaignStatus.draft
    )
    filters: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    audiences: Mapped[list["CampaignAudience"]] = relationship(
        "CampaignAudience", back_populates="campaign"
    )
    exports: Mapped[list["CampaignExport"]] = relationship(
        "CampaignExport", back_populates="campaign", order_by="CampaignExport.created_at.desc()"
    )
