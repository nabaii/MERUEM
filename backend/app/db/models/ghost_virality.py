"""Ghost Virality pipeline — ORM models.

Tables:
  ghost_scout_jobs        — scheduled scout runs
  ghost_reel_snapshots    — raw metadata captures per reel per scrape pass
  ghost_viral_posts       — posts flagged as Ghost Viral
  ghost_pattern_cards     — structural analysis per flagged post
  ghost_trial_reels       — trial reel tracking + A/B log
  ghost_niche_percentiles — per-niche like-count distribution cache
"""

import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class GhostJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class AudioType(str, enum.Enum):
    trending = "trending"
    original = "original"
    unknown = "unknown"


class StrategyLabel(str, enum.Enum):
    high_dm_share = "high_dm_share"
    watch_time_arbitrage = "watch_time_arbitrage"
    audio_driven = "audio_driven"
    polarizing = "polarizing"
    utility = "utility"
    unknown = "unknown"


class TrialReelStatus(str, enum.Enum):
    pending = "pending"
    live = "live"
    promoted = "promoted"
    rejected = "rejected"


# ---------------------------------------------------------------------------
# ghost_scout_jobs
# ---------------------------------------------------------------------------


class GhostScoutJob(Base):
    """Tracks a single scheduled or manual scouting run."""

    __tablename__ = "ghost_scout_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    niche: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    competitor_accounts: Mapped[Optional[list]] = mapped_column(JSONB)  # list[str]
    status: Mapped[GhostJobStatus] = mapped_column(
        Enum(GhostJobStatus, name="ghost_job_status_enum"),
        default=GhostJobStatus.pending,
        index=True,
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))
    reels_scraped: Mapped[int] = mapped_column(Integer, default=0)
    ghost_viral_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(2000))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# ---------------------------------------------------------------------------
# ghost_reel_snapshots
# ---------------------------------------------------------------------------


class GhostReelSnapshot(Base):
    """Raw metadata snapshot for a single Reel at a point in time.

    Two snapshots are taken per cycle (t0 and t1, ~4-6h apart) so that
    engagement velocity can be calculated.
    """

    __tablename__ = "ghost_reel_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reel_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    account_username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    niche: Mapped[Optional[str]] = mapped_column(String(120), index=True)

    # Counts at snapshot time
    view_count: Mapped[Optional[int]] = mapped_column(Integer)
    like_count: Mapped[Optional[int]] = mapped_column(Integer)
    comment_count: Mapped[Optional[int]] = mapped_column(Integer)
    follower_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Metadata
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    permalink: Mapped[Optional[str]] = mapped_column(String(1024))
    audio_id: Mapped[Optional[str]] = mapped_column(String(255))
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Which scout pass produced this snapshot (t0 / t1 for velocity)
    pass_index: Mapped[int] = mapped_column(Integer, default=0)
    scout_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True)

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_ghost_snapshots_reel_pass", "reel_id", "pass_index"),
    )


# ---------------------------------------------------------------------------
# ghost_viral_posts
# ---------------------------------------------------------------------------


class GhostViralPost(Base):
    """A Reel that passed both the Outlier Reach and Ghost Virality Delta filters."""

    __tablename__ = "ghost_viral_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reel_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    account_username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    niche: Mapped[Optional[str]] = mapped_column(String(120), index=True)

    # Core metrics
    view_count: Mapped[Optional[int]] = mapped_column(Integer)
    like_count: Mapped[Optional[int]] = mapped_column(Integer)
    comment_count: Mapped[Optional[int]] = mapped_column(Integer)
    follower_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Computed signals
    outlier_reach_ratio: Mapped[Optional[float]] = mapped_column(Float)   # view / follower
    ghost_virality_delta: Mapped[Optional[float]] = mapped_column(Float)  # view / like
    like_percentile: Mapped[Optional[float]] = mapped_column(Float)       # 0–100 within niche
    view_velocity: Mapped[Optional[float]] = mapped_column(Float)         # views/hr (t1-t0)
    like_velocity: Mapped[Optional[float]] = mapped_column(Float)         # likes/hr (t1-t0)

    # Strategy classification
    strategy_label: Mapped[Optional[StrategyLabel]] = mapped_column(
        Enum(StrategyLabel, name="ghost_strategy_label_enum"),
        nullable=True,
    )
    comment_sentiment: Mapped[Optional[str]] = mapped_column(String(20))  # positive/negative/neutral/mixed

    # Links
    permalink: Mapped[Optional[str]] = mapped_column(String(1024))
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024))
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Whether pattern recognition has been run
    pattern_card_ready: Mapped[bool] = mapped_column(default=False, index=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_ghost_viral_niche_delta", "niche", "ghost_virality_delta"),
        Index("ix_ghost_viral_detected", "detected_at"),
    )


# ---------------------------------------------------------------------------
# ghost_pattern_cards
# ---------------------------------------------------------------------------


class GhostPatternCard(Base):
    """Structural deconstruction of a Ghost Viral post.

    Produced by the pattern recognition pipeline (Sprint 3).
    """

    __tablename__ = "ghost_pattern_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ghost_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )

    # Hook analysis
    hook_duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    hook_clip_path: Mapped[Optional[str]] = mapped_column(String(1024))
    scene_cut_count: Mapped[Optional[int]] = mapped_column(Integer)

    # Transcript (Whisper)
    transcript_snippet: Mapped[Optional[str]] = mapped_column(Text)
    transcript_language: Mapped[Optional[str]] = mapped_column(String(10))
    transcript_confidence: Mapped[Optional[float]] = mapped_column(Float)

    # On-screen text (OCR)
    visual_text: Mapped[Optional[str]] = mapped_column(Text)

    # Audio
    audio_type: Mapped[Optional[AudioType]] = mapped_column(
        Enum(AudioType, name="ghost_audio_type_enum"), nullable=True
    )
    audio_id: Mapped[Optional[str]] = mapped_column(String(255))
    audio_name: Mapped[Optional[str]] = mapped_column(String(512))

    # Hook archetype (K-means cluster label, populated after 50+ cards)
    hook_archetype: Mapped[Optional[str]] = mapped_column(String(120))

    # Full structured card as JSON (for forward compatibility)
    raw_card: Mapped[Optional[dict]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# ghost_trial_reels
# ---------------------------------------------------------------------------


class GhostTrialReel(Base):
    """A Trial Reel derived from a scouted Ghost Viral pattern.

    Tracks creation → posting → performance → promotion decision.
    """

    __tablename__ = "ghost_trial_reels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ghost_post_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    niche: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    variation_label: Mapped[Optional[str]] = mapped_column(String(255))  # e.g. "Variation A"
    post_url: Mapped[Optional[str]] = mapped_column(String(1024))

    # Performance (manually entered or Graph API)
    views_at_1k: Mapped[Optional[int]] = mapped_column(Integer)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float)  # 0.0–1.0
    likes: Mapped[Optional[int]] = mapped_column(Integer)
    comments: Mapped[Optional[int]] = mapped_column(Integer)
    shares: Mapped[Optional[int]] = mapped_column(Integer)

    status: Mapped[TrialReelStatus] = mapped_column(
        Enum(TrialReelStatus, name="ghost_trial_status_enum"),
        default=TrialReelStatus.pending,
        index=True,
    )
    green_light: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    measured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


# ---------------------------------------------------------------------------
# ghost_niche_percentiles
# ---------------------------------------------------------------------------


class GhostNichePercentile(Base):
    """Cached like-count percentile distribution for a niche.

    Refreshed periodically. Used by the analytics engine to compute
    Ghost Virality Delta cross-references.
    """

    __tablename__ = "ghost_niche_percentiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    niche: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)

    # Percentile breakpoints (like counts)
    p10: Mapped[Optional[float]] = mapped_column(Float)
    p30: Mapped[Optional[float]] = mapped_column(Float)
    p50: Mapped[Optional[float]] = mapped_column(Float)
    p70: Mapped[Optional[float]] = mapped_column(Float)
    p90: Mapped[Optional[float]] = mapped_column(Float)

    # Outlier reach threshold for this niche (default 20)
    outlier_reach_threshold: Mapped[float] = mapped_column(Float, default=20.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
