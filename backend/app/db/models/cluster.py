from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.cluster_metric import ClusterMetric
    from app.db.models.social_profile import SocialProfile


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    top_interests: Mapped[Optional[dict]] = mapped_column(JSONB)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    social_profiles: Mapped[list["SocialProfile"]] = relationship(
        "SocialProfile", back_populates="cluster"
    )
    metrics: Mapped[list["ClusterMetric"]] = relationship(
        "ClusterMetric", back_populates="cluster"
    )
