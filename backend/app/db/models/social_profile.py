"""A single social media account on one platform."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.cluster import Cluster
    from app.db.models.post import Post
    from app.db.models.profile_interest import ProfileInterest
    from app.db.models.profile_link import ProfileLink
    from app.db.models.unified_user import UnifiedUser


class SocialProfile(Base):
    __tablename__ = "social_profiles"
    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_social_profiles_platform_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    unified_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("unified_users.id"), index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    bio: Mapped[Optional[str]] = mapped_column(String(1000))
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    location_raw: Mapped[Optional[str]] = mapped_column(String(255))
    location_inferred: Mapped[Optional[str]] = mapped_column(String(255))
    follower_count: Mapped[Optional[int]] = mapped_column(Integer)
    following_count: Mapped[Optional[int]] = mapped_column(Integer)
    tweet_count: Mapped[Optional[int]] = mapped_column(Integer)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    cluster_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("clusters.id"), index=True
    )
    verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    engagement_rate: Mapped[Optional[float]] = mapped_column(Float)
    affinity_score: Mapped[Optional[float]] = mapped_column(Float)
    source_method: Mapped[Optional[str]] = mapped_column(
        String(20), default="api", comment="api | bot | manual"
    )
    last_collected: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    embedding_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    unified_user: Mapped[Optional["UnifiedUser"]] = relationship(
        "UnifiedUser", back_populates="social_profiles"
    )
    cluster: Mapped[Optional["Cluster"]] = relationship(
        "Cluster", back_populates="social_profiles"
    )
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="social_profile")
    interests: Mapped[list["ProfileInterest"]] = relationship(
        "ProfileInterest", back_populates="social_profile"
    )
    outgoing_links: Mapped[list["ProfileLink"]] = relationship(
        "ProfileLink",
        foreign_keys="ProfileLink.source_profile_id",
        back_populates="source_profile",
    )
    incoming_links: Mapped[list["ProfileLink"]] = relationship(
        "ProfileLink",
        foreign_keys="ProfileLink.target_profile_id",
        back_populates="target_profile",
    )
