from __future__ import annotations

import io
import uuid
from collections import Counter
from datetime import datetime, timezone

from celery import chain
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func

from app.api.deps import CurrentAccount, DbDep
from app.core.config import settings
from app.db.models.profiling import LeadScore, ProfileAssessment, ProfilingJob
from app.db.models.social_profile import SocialProfile
from app.schemas.profiling import (
    AssessSingleRequest,
    AssessmentDetailOut,
    AssessmentListResponse,
    AssessmentOut,
    LeadScoreListResponse,
    LeadScoreOut,
    LeadScoreRecalculateRequest,
    LeadScoreRecalculateResponse,
    ProfileMiniOut,
    ProfilingJobCreate,
    ProfilingJobDetailOut,
    ProfilingJobOut,
    ProfilingStatsOut,
)
from app.services.export_service import ExportService
from app.services.profiling_service import (
    ProfilingConfigurationError,
    ProfilingService,
    select_profiles_for_profiling,
)
from app.services.scoring_service import DEFAULT_SCORING_WEIGHTS, ScoringService
from app.tasks.profiling_tasks import calculate_lead_scores, run_profiling_job

router = APIRouter(prefix="/profiling", tags=["profiling"])


def _profile_mini(profile: SocialProfile) -> ProfileMiniOut:
    return ProfileMiniOut.model_validate(profile)


def _assessment_out(assessment: ProfileAssessment, profile: SocialProfile | None) -> AssessmentOut:
    base = AssessmentOut.model_validate(assessment)
    if profile is not None:
        base.profile = _profile_mini(profile)
    return base


def _assessment_detail_out(
    assessment: ProfileAssessment,
    profile: SocialProfile | None,
) -> AssessmentDetailOut:
    base = AssessmentDetailOut.model_validate(assessment)
    if profile is not None:
        base.profile = _profile_mini(profile)
    return base


def _lead_score_out(
    lead_score: LeadScore,
    profile: SocialProfile,
) -> LeadScoreOut:
    base = LeadScoreOut.model_validate(lead_score)
    base.profile = _profile_mini(profile)
    return base


def _latest_lead_scores_query(db: DbDep):
    latest_subquery = (
        db.query(
            LeadScore.social_profile_id.label("social_profile_id"),
            func.max(LeadScore.created_at).label("latest_created_at"),
        )
        .group_by(LeadScore.social_profile_id)
        .subquery()
    )
    return (
        db.query(LeadScore, ProfileAssessment, SocialProfile)
        .join(
            latest_subquery,
            and_(
                LeadScore.social_profile_id == latest_subquery.c.social_profile_id,
                LeadScore.created_at == latest_subquery.c.latest_created_at,
            ),
        )
        .join(ProfileAssessment, ProfileAssessment.id == LeadScore.assessment_id)
        .join(SocialProfile, SocialProfile.id == LeadScore.social_profile_id)
    )


@router.post("/jobs", response_model=ProfilingJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_profiling_job(body: ProfilingJobCreate, _: CurrentAccount, db: DbDep):
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANTHROPIC_API_KEY is not configured",
        )

    profile_ids = select_profiles_for_profiling(
        db,
        body.filters,
        limit=settings.profiling_max_profiles_per_run,
    )
    metadata = {
        "filters": body.filters.model_dump(exclude_none=True),
        "profile_ids": [str(pid) for pid in profile_ids],
        "assessment_ids": [],
        "failed_profiles": [],
        "source": "api",
    }
    job = ProfilingJob(
        id=uuid.uuid4(),
        status="pending" if profile_ids else "completed",
        total_profiles=len(profile_ids),
        filters_used=metadata,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if profile_ids:
        result = chain(run_profiling_job.si(str(job.id)), calculate_lead_scores.s()).apply_async()
        job.filters_used = {**metadata, "task_id": result.id}
    else:
        job.completed_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    db.refresh(job)
    return ProfilingJobOut.model_validate(job)


@router.get("/jobs", response_model=list[ProfilingJobOut])
def list_profiling_jobs(_: CurrentAccount, db: DbDep, limit: int = Query(default=20, le=100)):
    jobs = (
        db.query(ProfilingJob)
        .order_by(ProfilingJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ProfilingJobOut.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=ProfilingJobDetailOut)
def get_profiling_job(job_id: uuid.UUID, _: CurrentAccount, db: DbDep):
    job = db.get(ProfilingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Profiling job not found")
    metadata = job.filters_used or {}
    return ProfilingJobDetailOut(
        **ProfilingJobOut.model_validate(job).model_dump(),
        profile_ids=metadata.get("profile_ids", []),
        assessment_ids=metadata.get("assessment_ids", []),
        failed_profiles=metadata.get("failed_profiles", []),
    )


@router.get("/assessments", response_model=AssessmentListResponse)
def list_assessments(
    _: CurrentAccount,
    db: DbDep,
    persona: str | None = Query(default=None),
    industry_fit: str | None = Query(default=None),
    min_purchase_intent: int | None = Query(default=None, ge=1, le=10),
    influence_tier: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(ProfileAssessment, SocialProfile).join(
        SocialProfile,
        SocialProfile.id == ProfileAssessment.social_profile_id,
    )

    if persona:
        query = query.filter(ProfileAssessment.persona == persona)
    if industry_fit:
        query = query.filter(ProfileAssessment.industry_fit.contains([industry_fit]))
    if min_purchase_intent is not None:
        query = query.filter(ProfileAssessment.purchase_intent_score >= min_purchase_intent)
    if influence_tier:
        query = query.filter(ProfileAssessment.influence_tier == influence_tier)
    if confidence:
        query = query.filter(ProfileAssessment.confidence == confidence)

    total = query.count()
    rows = (
        query.order_by(ProfileAssessment.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return AssessmentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_assessment_out(assessment, profile) for assessment, profile in rows],
    )


@router.get("/assessments/by-profile/{social_profile_id}", response_model=list[AssessmentOut])
def list_assessments_for_profile(
    social_profile_id: uuid.UUID,
    _: CurrentAccount,
    db: DbDep,
):
    profile = db.get(SocialProfile, social_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    assessments = (
        db.query(ProfileAssessment)
        .filter(ProfileAssessment.social_profile_id == social_profile_id)
        .order_by(ProfileAssessment.created_at.desc())
        .all()
    )
    return [_assessment_out(assessment, profile) for assessment in assessments]


@router.get("/assessments/{assessment_id}", response_model=AssessmentDetailOut)
def get_assessment(assessment_id: uuid.UUID, _: CurrentAccount, db: DbDep):
    assessment = db.get(ProfileAssessment, assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    profile = db.get(SocialProfile, assessment.social_profile_id)
    return _assessment_detail_out(assessment, profile)


@router.post("/assess-single", response_model=AssessmentDetailOut)
def assess_single_profile(body: AssessSingleRequest, _: CurrentAccount, db: DbDep):
    try:
        service = ProfilingService()
        assessment = service.assess_profile(db, body.social_profile_id, force=body.force)
        db.commit()
        profile = db.get(SocialProfile, assessment.social_profile_id)
        return _assessment_detail_out(assessment, profile)
    except ProfilingConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/lead-scores", response_model=LeadScoreListResponse)
def list_lead_scores(
    _: CurrentAccount,
    db: DbDep,
    min_score: float | None = Query(default=None, ge=0, le=100),
    tier: str | None = Query(default=None),
    target_industry: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = _latest_lead_scores_query(db)
    if min_score is not None:
        query = query.filter(LeadScore.total_score >= min_score)
    if tier:
        query = query.filter(LeadScore.tier == tier)
    if target_industry:
        query = query.filter(LeadScore.target_industries.contains([target_industry]))
    if platform:
        query = query.filter(SocialProfile.platform == platform)

    total = query.count()
    rows = query.order_by(LeadScore.total_score.desc()).offset(offset).limit(limit).all()
    return LeadScoreListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_lead_score_out(lead_score, profile) for lead_score, _, profile in rows],
    )


@router.post("/lead-scores/recalculate", response_model=LeadScoreRecalculateResponse)
def recalculate_lead_scores(
    body: LeadScoreRecalculateRequest,
    _: CurrentAccount,
    db: DbDep,
):
    scoring_service = ScoringService()
    merged_weights = {**DEFAULT_SCORING_WEIGHTS, **(body.weights or {})}
    recalculated = scoring_service.recalculate_all_scores(db, weights=body.weights)
    db.commit()
    return LeadScoreRecalculateResponse(recalculated=recalculated, weights=merged_weights)


@router.get("/export/csv")
def export_csv(
    _: CurrentAccount,
    db: DbDep,
    platform: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    target_industry: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
):
    query = _latest_lead_scores_query(db)
    if platform:
        query = query.filter(SocialProfile.platform == platform)
    if tier:
        query = query.filter(LeadScore.tier == tier)
    if target_industry:
        query = query.filter(LeadScore.target_industries.contains([target_industry]))
    if min_score is not None:
        query = query.filter(LeadScore.total_score >= min_score)
    rows = query.order_by(LeadScore.total_score.desc()).all()

    data = ExportService().build_generic_csv(rows)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="profiling-leads.csv"'},
    )


@router.get("/export/hubspot")
def export_hubspot(
    _: CurrentAccount,
    db: DbDep,
    platform: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    target_industry: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
):
    query = _latest_lead_scores_query(db)
    if platform:
        query = query.filter(SocialProfile.platform == platform)
    if tier:
        query = query.filter(LeadScore.tier == tier)
    if target_industry:
        query = query.filter(LeadScore.target_industries.contains([target_industry]))
    if min_score is not None:
        query = query.filter(LeadScore.total_score >= min_score)
    rows = query.order_by(LeadScore.total_score.desc()).all()

    data = ExportService().build_hubspot_csv(rows)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="profiling-leads-hubspot.csv"'},
    )


@router.get("/stats", response_model=ProfilingStatsOut)
def profiling_stats(_: CurrentAccount, db: DbDep):
    assessments = db.query(ProfileAssessment).all()
    latest_rows = _latest_lead_scores_query(db).all()

    persona_distribution = Counter(
        assessment.persona or "Unknown" for assessment in assessments
    )
    purchase_intent_scores = [
        assessment.purchase_intent_score
        for assessment in assessments
        if assessment.purchase_intent_score is not None
    ]
    tier_breakdown = Counter((lead_score.tier or "Unknown") for lead_score, _, _ in latest_rows)
    top_industries = Counter()
    for _, assessment, _ in latest_rows:
        top_industries.update(assessment.industry_fit or [])

    avg_purchase_intent = (
        round(sum(purchase_intent_scores) / len(purchase_intent_scores), 4)
        if purchase_intent_scores
        else None
    )
    return ProfilingStatsOut(
        total_assessed=len(assessments),
        persona_distribution=dict(persona_distribution),
        avg_purchase_intent=avg_purchase_intent,
        tier_breakdown=dict(tier_breakdown),
        top_industries=dict(top_industries.most_common(10)),
    )
