import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class TiktokMetricSnapshot(Base):
    __tablename__ = "tiktok_metric_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    
    # Raw snapshot metrics from tiktok
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    avg_watch_time: Mapped[Optional[float]] = mapped_column(Float)
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

class TiktokVelocityScore(Base):
    __tablename__ = "tiktok_velocity_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tiktok_metric_snapshots.id", ondelete="CASCADE"))
    
    score: Mapped[float] = mapped_column(Float)
    velocity_rate: Mapped[float] = mapped_column(Float)
    is_breakout: Mapped[bool] = mapped_column(Boolean, default=False)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SparkAdEvent(Base):
    __tablename__ = "spark_ad_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"))
    
    campaign_id: Mapped[Optional[str]] = mapped_column(String(255))
    budget: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50)) # e.g. "pending", "active", "completed", "failed"
    
    cpm: Mapped[Optional[float]] = mapped_column(Float)
    cpc: Mapped[Optional[float]] = mapped_column(Float)
    cpa: Mapped[Optional[float]] = mapped_column(Float)
    roas: Mapped[Optional[float]] = mapped_column(Float)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TiktokAuditReport(Base):
    __tablename__ = "tiktok_audit_reports"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"))
    
    file_path: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50)) # "processing", "completed", "failed"
    
    # Audit component scores (pass/fail or raw float)
    asr_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    ocr_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    caption_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    audio_clarity_score: Mapped[Optional[float]] = mapped_column(Float)
    hashtags_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    overall_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Full json report dump for dashboard visualization
    raw_report: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

