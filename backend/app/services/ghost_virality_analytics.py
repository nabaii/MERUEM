"""Ghost Virality Analytics Service.

Implements:
  - Outlier Reach filter  (view / follower >= threshold)
  - Niche percentile engine (like-count distribution per niche)
  - Ghost Virality Delta score (view / like, cross-referenced against percentile)
  - Engagement velocity tracking (view/like rates between two snapshots)
  - Strategy label assignment
  - Niche drift detection (z-score on rolling 30-day delta averages)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.db.models.ghost_virality import (
    GhostNichePercentile,
    GhostReelSnapshot,
    GhostViralPost,
    StrategyLabel,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (all configurable per-niche via GhostNichePercentile)
# ---------------------------------------------------------------------------

DEFAULT_OUTLIER_REACH_THRESHOLD = 20.0   # view/follower ratio
GHOST_VIRAL_LIKE_PERCENTILE_MAX = 30.0   # like count must be in bottom 30th percentile
MIN_NICHE_SAMPLES = 200                  # min posts for valid percentile calculation
NICHE_DRIFT_ZSCORE = 2.0                 # z-score threshold for drift alert
VELOCITY_WINDOW_HOURS = 6               # expected gap between t0 and t1 snapshots


# ---------------------------------------------------------------------------
# Percentile Engine
# ---------------------------------------------------------------------------


def refresh_niche_percentiles(niche: str, db: Session) -> GhostNichePercentile:
    """Recompute like-count percentiles for a niche from all stored snapshots.

    Requires >= MIN_NICHE_SAMPLES to be statistically meaningful.
    Upserts a GhostNichePercentile row.
    """
    rows = (
        db.query(GhostReelSnapshot.like_count)
        .filter(
            GhostReelSnapshot.niche == niche,
            GhostReelSnapshot.like_count.isnot(None),
            GhostReelSnapshot.pass_index == 0,  # use t0 snapshot
        )
        .all()
    )

    like_counts = [r.like_count for r in rows if r.like_count is not None]

    record = db.query(GhostNichePercentile).filter(GhostNichePercentile.niche == niche).first()
    if record is None:
        record = GhostNichePercentile(id=uuid.uuid4(), niche=niche)
        db.add(record)

    record.sample_size = len(like_counts)

    if len(like_counts) >= MIN_NICHE_SAMPLES:
        arr = np.array(like_counts, dtype=float)
        record.p10 = float(np.percentile(arr, 10))
        record.p30 = float(np.percentile(arr, 30))
        record.p50 = float(np.percentile(arr, 50))
        record.p70 = float(np.percentile(arr, 70))
        record.p90 = float(np.percentile(arr, 90))
    else:
        log.info(
            "Niche '%s' has only %d samples — percentiles not yet reliable",
            niche, len(like_counts),
        )

    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


def get_like_percentile(like_count: int, percentile_row: GhostNichePercentile) -> Optional[float]:
    """Return approximate percentile rank (0–100) for a given like_count in a niche.

    Uses linear interpolation between stored breakpoints.
    Returns None if percentile data is not yet available.
    """
    if percentile_row.p10 is None:
        return None

    breakpoints = [
        (0.0, 0.0),
        (percentile_row.p10, 10.0),
        (percentile_row.p30, 30.0),
        (percentile_row.p50, 50.0),
        (percentile_row.p70, 70.0),
        (percentile_row.p90, 90.0),
    ]

    if like_count <= 0:
        return 0.0

    for i in range(1, len(breakpoints)):
        lo_val, lo_pct = breakpoints[i - 1]
        hi_val, hi_pct = breakpoints[i]
        if hi_val is None:
            continue
        if lo_val <= like_count <= hi_val:
            if hi_val == lo_val:
                return lo_pct
            frac = (like_count - lo_val) / (hi_val - lo_val)
            return lo_pct + frac * (hi_pct - lo_pct)

    # Above p90
    return 95.0


# ---------------------------------------------------------------------------
# Velocity Calculation
# ---------------------------------------------------------------------------


def compute_velocity(
    snap_t0: GhostReelSnapshot,
    snap_t1: GhostReelSnapshot,
) -> tuple[Optional[float], Optional[float]]:
    """Calculate view and like velocity (units per hour) between two snapshots.

    Returns (view_velocity, like_velocity).
    """
    if snap_t0.scraped_at is None or snap_t1.scraped_at is None:
        return None, None

    hours = (snap_t1.scraped_at - snap_t0.scraped_at).total_seconds() / 3600.0
    if hours < 0.1:
        return None, None

    view_vel: Optional[float] = None
    like_vel: Optional[float] = None

    if snap_t0.view_count is not None and snap_t1.view_count is not None:
        view_vel = (snap_t1.view_count - snap_t0.view_count) / hours

    if snap_t0.like_count is not None and snap_t1.like_count is not None:
        like_vel = (snap_t1.like_count - snap_t0.like_count) / hours

    return view_vel, like_vel


# ---------------------------------------------------------------------------
# Core Filter — flag_ghost_viral
# ---------------------------------------------------------------------------


def flag_ghost_viral(
    snap_t0: GhostReelSnapshot,
    snap_t1: Optional[GhostReelSnapshot],
    percentile_row: Optional[GhostNichePercentile],
    db: Session,
) -> Optional[GhostViralPost]:
    """Evaluate a Reel snapshot pair against the Ghost Virality filters.

    Returns a persisted GhostViralPost if it passes, else None.

    Filters applied:
    1. Outlier Reach  — view / follower >= threshold
    2. Ghost Virality Delta — view / like ratio
    3. Low likes  — like_count in bottom 30th percentile of niche
       (skipped if percentile data is unavailable — stricter check below)
    """
    view_count = snap_t0.view_count or 0
    like_count = snap_t0.like_count or 0
    follower_count = snap_t0.follower_count or 1  # avoid division by zero

    # ---- Filter 1: Outlier Reach
    threshold = (
        percentile_row.outlier_reach_threshold
        if percentile_row
        else DEFAULT_OUTLIER_REACH_THRESHOLD
    )
    outlier_reach_ratio = view_count / follower_count
    if outlier_reach_ratio < threshold:
        return None

    # ---- Filter 2: Ghost Virality Delta
    if like_count == 0:
        # No likes at all is the strongest possible ghost viral signal
        ghost_virality_delta = float("inf")
        like_percentile = 0.0
    else:
        ghost_virality_delta = view_count / like_count

        # ---- Filter 3: Like percentile (soft gate — apply only when data is ready)
        like_percentile = None
        if percentile_row and percentile_row.p30 is not None:
            like_percentile = get_like_percentile(like_count, percentile_row)
            if like_percentile is not None and like_percentile > GHOST_VIRAL_LIKE_PERCENTILE_MAX:
                return None
        else:
            # Without percentile data, require an extremely high view/like ratio
            if ghost_virality_delta < 50:
                return None

    # ---- Velocity (if t1 available)
    view_velocity, like_velocity = None, None
    if snap_t1:
        view_velocity, like_velocity = compute_velocity(snap_t0, snap_t1)

    # ---- Strategy label
    strategy = _assign_strategy(
        ghost_virality_delta=ghost_virality_delta,
        view_velocity=view_velocity,
        like_velocity=like_velocity,
        audio_id=snap_t0.audio_id,
    )

    # ---- Persist / upsert
    existing = (
        db.query(GhostViralPost)
        .filter(GhostViralPost.reel_id == snap_t0.reel_id)
        .first()
    )

    if existing:
        # Update metrics but don't overwrite pattern_card_ready
        existing.view_count = view_count
        existing.like_count = like_count
        existing.follower_count = snap_t0.follower_count
        existing.outlier_reach_ratio = outlier_reach_ratio
        existing.ghost_virality_delta = ghost_virality_delta if ghost_virality_delta != float("inf") else 9999.0
        existing.like_percentile = like_percentile
        existing.view_velocity = view_velocity
        existing.like_velocity = like_velocity
        existing.strategy_label = strategy
        db.add(existing)
        db.commit()
        return existing

    post = GhostViralPost(
        id=uuid.uuid4(),
        reel_id=snap_t0.reel_id,
        account_username=snap_t0.account_username,
        niche=snap_t0.niche,
        view_count=view_count,
        like_count=like_count,
        comment_count=snap_t0.comment_count,
        follower_count=snap_t0.follower_count,
        outlier_reach_ratio=outlier_reach_ratio,
        ghost_virality_delta=ghost_virality_delta if ghost_virality_delta != float("inf") else 9999.0,
        like_percentile=like_percentile,
        view_velocity=view_velocity,
        like_velocity=like_velocity,
        strategy_label=strategy,
        permalink=snap_t0.permalink,
        thumbnail_url=snap_t0.thumbnail_url,
        posted_at=snap_t0.posted_at,
        pattern_card_ready=False,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


# ---------------------------------------------------------------------------
# Strategy Classification
# ---------------------------------------------------------------------------


def _assign_strategy(
    ghost_virality_delta: float,
    view_velocity: Optional[float],
    like_velocity: Optional[float],
    audio_id: Optional[str],
) -> StrategyLabel:
    """Rule-based strategy label assignment per the plan spec."""
    # Audio-Driven: trending audio present
    if audio_id:
        return StrategyLabel.audio_driven

    # Watch Time Arbitrage: views accelerating, likes flat or decelerating
    if view_velocity and like_velocity is not None:
        if view_velocity > 0 and like_velocity <= 0:
            return StrategyLabel.watch_time_arbitrage

    # High DM Share Potential: very high view/like gap
    if ghost_virality_delta > 100:
        return StrategyLabel.high_dm_share

    return StrategyLabel.unknown


# ---------------------------------------------------------------------------
# Niche Drift Detection
# ---------------------------------------------------------------------------


def check_niche_drift(niche: str, db: Session) -> Optional[dict]:
    """Compute z-score of recent 7-day avg delta vs rolling 30-day avg delta.

    Returns a drift alert dict if z-score exceeds NICHE_DRIFT_ZSCORE, else None.
    """
    now = datetime.now(timezone.utc)
    window_30d = now - timedelta(days=30)
    window_7d = now - timedelta(days=7)

    all_posts = (
        db.query(GhostViralPost.ghost_virality_delta, GhostViralPost.detected_at)
        .filter(
            GhostViralPost.niche == niche,
            GhostViralPost.detected_at >= window_30d,
            GhostViralPost.ghost_virality_delta.isnot(None),
        )
        .all()
    )

    if len(all_posts) < 10:
        return None

    deltas_30d = [r.ghost_virality_delta for r in all_posts]
    deltas_7d = [
        r.ghost_virality_delta for r in all_posts
        if r.detected_at >= window_7d
    ]

    if not deltas_7d:
        return None

    mean_30d = float(np.mean(deltas_30d))
    std_30d = float(np.std(deltas_30d))
    mean_7d = float(np.mean(deltas_7d))

    if std_30d < 1e-6:
        return None

    z = (mean_7d - mean_30d) / std_30d
    if abs(z) < NICHE_DRIFT_ZSCORE:
        return None

    direction = "spiking" if z > 0 else "shrinking"
    return {
        "niche": niche,
        "z_score": round(z, 2),
        "direction": direction,
        "mean_30d": round(mean_30d, 2),
        "mean_7d": round(mean_7d, 2),
        "message": (
            f"Niche '{niche}' Ghost Viral delta is {direction} "
            f"(z={z:.2f}, 7d avg={mean_7d:.1f} vs 30d avg={mean_30d:.1f})"
        ),
    }
