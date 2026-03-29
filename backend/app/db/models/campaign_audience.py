import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.campaign import Campaign
    from app.db.models.cluster import Cluster


class ExportStatus(str, enum.Enum):
    pending = "pending"
    exported = "exported"
    failed = "failed"


class CampaignAudience(Base):
    __tablename__ = "campaign_audiences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    cluster_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("clusters.id"), index=True
    )
    estimated_reach: Mapped[Optional[int]] = mapped_column(Integer)
    export_status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status_enum"), default=ExportStatus.pending
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="audiences")
    cluster: Mapped[Optional["Cluster"]] = relationship("Cluster")
