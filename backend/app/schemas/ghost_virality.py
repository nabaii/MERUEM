"""Pydantic schemas for the Ghost Virality pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Scout Jobs
# ---------------------------------------------------------------------------


class GhostScoutJobCreate(BaseModel):
    niche: str = Field(..., min_length=1, max_length=120, description="Content niche (e.g. 'fitness', 'finance')")
    competitor_accounts: list[str] = Field(default_factory=list, description="Instagram usernames to scout")


class GhostScoutJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    niche: str
    competitor_accounts: Optional[list] = None
    status: str
    celery_task_id: Optional[str] = None
    reels_scraped: int
    ghost_viral_found: int
    error_message: Optional[str] = None
    created_by: Optional[uuid.UUID] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Pattern Card
# ---------------------------------------------------------------------------


class PatternCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ghost_post_id: uuid.UUID
    hook_duration_seconds: Optional[float] = None
    hook_clip_path: Optional[str] = None
    scene_cut_count: Optional[int] = None
    transcript_snippet: Optional[str] = None
    transcript_language: Optional[str] = None
    transcript_confidence: Optional[float] = None
    visual_text: Optional[str] = None
    audio_type: Optional[str] = None
    audio_id: Optional[str] = None
    audio_name: Optional[str] = None
    hook_archetype: Optional[str] = None
    raw_card: Optional[dict] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Ghost Viral Posts
# ---------------------------------------------------------------------------


class GhostViralPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reel_id: str
    account_username: str
    niche: Optional[str] = None

    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    follower_count: Optional[int] = None

    outlier_reach_ratio: Optional[float] = None
    ghost_virality_delta: Optional[float] = None
    like_percentile: Optional[float] = None
    view_velocity: Optional[float] = None
    like_velocity: Optional[float] = None

    strategy_label: Optional[str] = None
    comment_sentiment: Optional[str] = None

    permalink: Optional[str] = None
    thumbnail_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    pattern_card_ready: bool
    detected_at: datetime

    pattern_card: Optional[PatternCardOut] = None


# ---------------------------------------------------------------------------
# Niche Overview
# ---------------------------------------------------------------------------


class NicheOverviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    niche: str
    sample_size: int
    p10: Optional[float] = None
    p30: Optional[float] = None
    p50: Optional[float] = None
    p70: Optional[float] = None
    p90: Optional[float] = None
    outlier_reach_threshold: float
    ghost_viral_count: Optional[int] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Trial Reels
# ---------------------------------------------------------------------------


class TrialReelCreate(BaseModel):
    ghost_post_id: Optional[uuid.UUID] = None
    niche: Optional[str] = Field(None, max_length=120)
    variation_label: Optional[str] = Field(None, max_length=255)
    post_url: Optional[str] = Field(None, max_length=1024)
    notes: Optional[str] = None


class TrialReelUpdate(BaseModel):
    post_url: Optional[str] = Field(None, max_length=1024)
    views_at_1k: Optional[int] = None
    completion_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    status: Optional[str] = None
    green_light: Optional[bool] = None
    notes: Optional[str] = None
    posted_at: Optional[datetime] = None
    measured_at: Optional[datetime] = None


class TrialReelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ghost_post_id: Optional[uuid.UUID] = None
    niche: Optional[str] = None
    variation_label: Optional[str] = None
    post_url: Optional[str] = None
    views_at_1k: Optional[int] = None
    completion_rate: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    status: str
    green_light: bool
    notes: Optional[str] = None
    posted_at: Optional[datetime] = None
    measured_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------


class GhostViralityStats(BaseModel):
    total_ghost_posts: int
    new_last_7_days: int
    pattern_cards_ready: int
    active_scout_jobs: int
    trial_reels_total: int
    trial_reels_green_lit: int
    top_niches: list[dict]
