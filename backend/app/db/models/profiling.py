import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.social_profile import SocialProfile
    from app.db.models.unified_user import UnifiedUser


class ProfileAssessment(Base):
    __tablename__ = "profile_assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    social_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unified_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unified_users.id", ondelete="SET NULL"),
        index=True,
    )
    persona: Mapped[Optional[str]] = mapped_column(String(100))
    primary_interests: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    secondary_interests: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    sentiment_tone: Mapped[Optional[str]] = mapped_column(String(50))
    purchase_intent_score: Mapped[Optional[int]] = mapped_column(Integer)
    influence_tier: Mapped[Optional[str]] = mapped_column(String(20))
    engagement_style: Mapped[Optional[str]] = mapped_column(String(50))
    psychographic_driver: Mapped[Optional[str]] = mapped_column(String(50))
    recommended_channel: Mapped[Optional[str]] = mapped_column(String(50))
    recommended_message_angle: Mapped[Optional[str]] = mapped_column(Text)
    industry_fit: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    confidence: Mapped[Optional[str]] = mapped_column(String(30))
    raw_llm_response: Mapped[Optional[str]] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    social_profile: Mapped["SocialProfile"] = relationship("SocialProfile")
    unified_user: Mapped[Optional["UnifiedUser"]] = relationship("UnifiedUser")


class LeadScore(Base):
    __tablename__ = "lead_scores"
    __table_args__ = (UniqueConstraint("assessment_id", name="uq_lead_scores_assessment_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    social_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profile_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB)
    tier: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    target_industries: Mapped[Optional[list[str]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    social_profile: Mapped["SocialProfile"] = relationship("SocialProfile")
    assessment: Mapped["ProfileAssessment"] = relationship("ProfileAssessment")


class ProfilingJob(Base):
    __tablename__ = "profiling_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    total_profiles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filters_used: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
