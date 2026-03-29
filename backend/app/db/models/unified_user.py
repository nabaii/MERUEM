"""Unified cross-platform identity — one row per real person."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.profile_link import ProfileLink
    from app.db.models.social_profile import SocialProfile


class UnifiedUser(Base):
    __tablename__ = "unified_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    canonical_name: Mapped[Optional[str]] = mapped_column(String(255))
    canonical_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    canonical_location: Mapped[Optional[str]] = mapped_column(String(255))
    merged_embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    merged_interests: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    social_profiles: Mapped[list["SocialProfile"]] = relationship(
        "SocialProfile", back_populates="unified_user"
    )
    profile_links: Mapped[list["ProfileLink"]] = relationship(
        "ProfileLink",
        foreign_keys="ProfileLink.unified_user_id",
        back_populates="unified_user",
    )
