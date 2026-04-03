"""Ghost Virality API routes — Sprint 4 dashboard endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAccount, DbDep
from app.db.models.ghost_virality import (
    GhostJobStatus,
    GhostNichePercentile,
    GhostPatternCard,
    GhostScoutJob,
    GhostTrialReel,
    GhostViralPost,
    TrialReelStatus,
)
from app.schemas.ghost_virality import (
    GhostScoutJobCreate,
    GhostScoutJobOut,
    GhostViralityStats,
    GhostViralPostOut,
    NicheOverviewOut,
    PatternCardOut,
    TrialReelCreate,
    TrialReelOut,
    TrialReelUpdate,
)

router = APIRouter(prefix="/ghost-virality", tags=["ghost-virality"])


# ---------------------------------------------------------------------------
# Scout Jobs
# ---------------------------------------------------------------------------


@router.post(
    "/scout-jobs",
    response_model=GhostScoutJobOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_scout_job(
    payload: GhostScoutJobCreate,
    account: CurrentAccount,
    db: DbDep,
):
    """Start a new Ghost Virality scouting run for a niche."""
    from app.tasks.ghost_virality import run_ghost_scout_job

    job = GhostScoutJob(
        id=uuid.uuid4(),
        niche=payload.niche,
        competitor_accounts=payload.competitor_accounts,
        status=GhostJobStatus.pending,
        created_by=account.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    task = run_ghost_scout_job.apply_async(args=[str(job.id)], queue="ghost_scout")
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/scout-jobs", response_model=list[GhostScoutJobOut])
def list_scout_jobs(
    account: CurrentAccount,
    db: DbDep,
    limit: int = Query(20, le=100),
):
    return (
        db.query(GhostScoutJob)
        .order_by(GhostScoutJob.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/scout-jobs/{job_id}", response_model=GhostScoutJobOut)
def get_scout_job(job_id: UUID, _: CurrentAccount, db: DbDep):
    job = db.query(GhostScoutJob).filter(GhostScoutJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Scout job not found")
    return job


# ---------------------------------------------------------------------------
# Ghost Viral Posts (Ghost Feed)
# ---------------------------------------------------------------------------


@router.get("/ghosts", response_model=list[GhostViralPostOut])
def list_ghost_posts(
    account: CurrentAccount,
    db: DbDep,
    niche: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90, description="Recency window in days"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    """Paginated Ghost Feed — sortable by ghost_virality_delta descending."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        db.query(GhostViralPost)
        .filter(GhostViralPost.detected_at >= since)
        .order_by(GhostViralPost.ghost_virality_delta.desc().nulls_last())
    )
    if niche:
        q = q.filter(GhostViralPost.niche == niche)
    if strategy:
        q = q.filter(GhostViralPost.strategy_label == strategy)

    posts = q.offset(offset).limit(limit).all()
    return posts


@router.get("/ghosts/{post_id}", response_model=GhostViralPostOut)
def get_ghost_post(post_id: UUID, _: CurrentAccount, db: DbDep):
    """Post detail — includes pattern card if available."""
    post = db.query(GhostViralPost).filter(GhostViralPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Ghost Viral post not found")

    # Attach pattern card
    card = (
        db.query(GhostPatternCard)
        .filter(GhostPatternCard.ghost_post_id == post_id)
        .first()
    )

    result = GhostViralPostOut.model_validate(post)
    if card:
        result.pattern_card = PatternCardOut.model_validate(card)
    return result


# ---------------------------------------------------------------------------
# Niches
# ---------------------------------------------------------------------------


@router.get("/niches", response_model=list[NicheOverviewOut])
def list_niches(_: CurrentAccount, db: DbDep):
    """Niche heatmap data — percentile stats + Ghost Viral count per niche."""
    percentile_rows = db.query(GhostNichePercentile).all()

    results = []
    for row in percentile_rows:
        count = (
            db.query(GhostViralPost)
            .filter(GhostViralPost.niche == row.niche)
            .count()
        )
        out = NicheOverviewOut.model_validate(row)
        out.ghost_viral_count = count
        results.append(out)

    return sorted(results, key=lambda r: r.ghost_viral_count or 0, reverse=True)


# ---------------------------------------------------------------------------
# Stats summary
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=GhostViralityStats)
def get_stats(_: CurrentAccount, db: DbDep):
    """Dashboard summary stats for the Ghost Virality module."""
    since_7d = datetime.now(timezone.utc) - timedelta(days=7)

    total = db.query(GhostViralPost).count()
    new_7d = db.query(GhostViralPost).filter(GhostViralPost.detected_at >= since_7d).count()
    cards_ready = db.query(GhostViralPost).filter(GhostViralPost.pattern_card_ready.is_(True)).count()
    active_jobs = (
        db.query(GhostScoutJob)
        .filter(GhostScoutJob.status.in_([GhostJobStatus.pending, GhostJobStatus.running]))
        .count()
    )
    trial_total = db.query(GhostTrialReel).count()
    trial_green = db.query(GhostTrialReel).filter(GhostTrialReel.green_light.is_(True)).count()

    # Top niches by count
    from sqlalchemy import func
    top_niches_q = (
        db.query(GhostViralPost.niche, func.count(GhostViralPost.id).label("count"))
        .filter(GhostViralPost.niche.isnot(None))
        .group_by(GhostViralPost.niche)
        .order_by(func.count(GhostViralPost.id).desc())
        .limit(5)
        .all()
    )
    top_niches = [{"niche": r.niche, "count": r.count} for r in top_niches_q]

    return GhostViralityStats(
        total_ghost_posts=total,
        new_last_7_days=new_7d,
        pattern_cards_ready=cards_ready,
        active_scout_jobs=active_jobs,
        trial_reels_total=trial_total,
        trial_reels_green_lit=trial_green,
        top_niches=top_niches,
    )


# ---------------------------------------------------------------------------
# Trial Reels
# ---------------------------------------------------------------------------


@router.post("/trial-reels", response_model=TrialReelOut, status_code=status.HTTP_201_CREATED)
def create_trial_reel(payload: TrialReelCreate, account: CurrentAccount, db: DbDep):
    """Log a new Trial Reel derived from a scouted pattern."""
    trial = GhostTrialReel(
        id=uuid.uuid4(),
        ghost_post_id=payload.ghost_post_id,
        niche=payload.niche,
        variation_label=payload.variation_label,
        post_url=payload.post_url,
        notes=payload.notes,
        status=TrialReelStatus.pending,
        created_by=account.id,
    )
    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


@router.get("/trial-reels", response_model=list[TrialReelOut])
def list_trial_reels(
    _: CurrentAccount,
    db: DbDep,
    niche: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    q = db.query(GhostTrialReel).order_by(GhostTrialReel.created_at.desc())
    if niche:
        q = q.filter(GhostTrialReel.niche == niche)
    return q.limit(limit).all()


@router.get("/trial-reels/{trial_id}", response_model=TrialReelOut)
def get_trial_reel(trial_id: UUID, _: CurrentAccount, db: DbDep):
    trial = db.query(GhostTrialReel).filter(GhostTrialReel.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial Reel not found")
    return trial


@router.patch("/trial-reels/{trial_id}", response_model=TrialReelOut)
def update_trial_reel(
    trial_id: UUID,
    payload: TrialReelUpdate,
    _: CurrentAccount,
    db: DbDep,
):
    """Update performance metrics on a Trial Reel.

    Auto-sets green_light=True when completion_rate >= 0.85.
    """
    trial = db.query(GhostTrialReel).filter(GhostTrialReel.id == trial_id).first()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial Reel not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(trial, field, value)

    # Auto green-light when completion rate threshold is met
    if trial.completion_rate is not None and trial.completion_rate >= 0.85:
        trial.green_light = True
        trial.status = TrialReelStatus.promoted

    db.add(trial)
    db.commit()
    db.refresh(trial)
    return trial


# ---------------------------------------------------------------------------
# Pattern card (standalone endpoint)
# ---------------------------------------------------------------------------


@router.get("/ghosts/{post_id}/pattern-card", response_model=PatternCardOut)
def get_pattern_card(post_id: UUID, _: CurrentAccount, db: DbDep):
    card = (
        db.query(GhostPatternCard)
        .filter(GhostPatternCard.ghost_post_id == post_id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Pattern card not yet available for this post")
    return card


@router.post(
    "/ghosts/{post_id}/pattern-card/retry",
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_pattern_recognition(post_id: UUID, _: CurrentAccount, db: DbDep):
    """Re-queue pattern recognition for a post (e.g. after video download completes)."""
    post = db.query(GhostViralPost).filter(GhostViralPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Ghost Viral post not found")

    # Delete existing card so it gets rebuilt
    db.query(GhostPatternCard).filter(GhostPatternCard.ghost_post_id == post_id).delete()
    post.pattern_card_ready = False
    db.add(post)
    db.commit()

    from app.tasks.ghost_virality import run_ghost_pattern_recognition
    run_ghost_pattern_recognition.apply_async(args=[str(post_id)], queue="ghost_pattern")

    return {"status": "queued", "post_id": str(post_id)}
