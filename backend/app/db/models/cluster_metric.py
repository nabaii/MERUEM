import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.cluster import Cluster


class ClusterMetric(Base):
    __tablename__ = "cluster_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clusters.id"), nullable=False, index=True
    )
    avg_engagement: Mapped[Optional[float]] = mapped_column(Float)
    avg_followers: Mapped[Optional[float]] = mapped_column(Float)
    interest_distribution: Mapped[Optional[dict]] = mapped_column(JSONB)
    computed_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cluster: Mapped["Cluster"] = relationship("Cluster", back_populates="metrics")
