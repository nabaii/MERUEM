import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.social_profile import SocialProfile


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("social_profiles.id"), nullable=False, index=True
    )
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    content: Mapped[Optional[str]] = mapped_column(String(4000))
    post_type: Mapped[Optional[str]] = mapped_column(String(50))  # tweet, reply, retweet, like
    likes: Mapped[Optional[int]] = mapped_column(Integer)
    reposts: Mapped[Optional[int]] = mapped_column(Integer)
    replies: Mapped[Optional[int]] = mapped_column(Integer)
    entities: Mapped[Optional[dict]] = mapped_column(JSONB)  # hashtags, mentions, urls
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    social_profile: Mapped["SocialProfile"] = relationship(
        "SocialProfile", back_populates="posts"
    )
