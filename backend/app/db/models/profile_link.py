"""Cross-platform identity resolution links."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.social_profile import SocialProfile
    from app.db.models.unified_user import UnifiedUser


class LinkStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class ProfileLink(Base):
    __tablename__ = "profile_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    unified_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("unified_users.id"), index=True
    )
    source_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_profiles.id"), nullable=False
    )
    target_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_profiles.id"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    match_method: Mapped[str] = mapped_column(String(100), nullable=False)  # name, bio_url, email
    status: Mapped[LinkStatus] = mapped_column(
        Enum(LinkStatus, name="link_status_enum"), default=LinkStatus.pending
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    unified_user: Mapped[Optional["UnifiedUser"]] = relationship(
        "UnifiedUser",
        foreign_keys=[unified_user_id],
        back_populates="profile_links",
    )
    source_profile: Mapped["SocialProfile"] = relationship(
        "SocialProfile",
        foreign_keys=[source_profile_id],
        back_populates="outgoing_links",
    )
    target_profile: Mapped["SocialProfile"] = relationship(
        "SocialProfile",
        foreign_keys=[target_profile_id],
        back_populates="incoming_links",
    )
