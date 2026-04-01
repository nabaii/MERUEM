from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from celery import Task
from sqlalchemy import and_, func

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.models.profiling import LeadScore, ProfileAssessment, ProfilingJob
from app.db.models.social_profile import SocialProfile
from app.db.session import SessionLocal
from app.schemas.profiling import ProfilingFilters
from app.services.export_service import ExportService
from app.services.profiling_service import ProfilingService, select_profiles_for_profiling
from app.services.scoring_service import ScoringService

log = logging.getLogger(__name__)


def _update_job_metadata(job: ProfilingJob, **updates: Any) -> dict[str, Any]:
    metadata = dict(job.filters_used or {})
    metadata.update(updates)
    job.filters_used = metadata
    return metadata


def _execute_profiling_job(job: ProfilingJob) -> dict[str, Any]:
    service = ProfilingService()
    interval = 60.0 / max(settings.profiling_rate_limit_per_minute, 1)
    successful_ids: list[str] = list((job.filters_used or {}).get("assessment_ids", []))
    failed_profiles: list[dict[str, str]] = list((job.filters_used or {}).get("failed_profiles", []))
    profile_ids = [uuid.UUID(pid) for pid in (job.filters_used or {}).get("profile_ids", [])]

    with SessionLocal() as db:
        db_job = db.get(ProfilingJob, job.id)
        if not db_job:
            return {"error": "job not found", "job_id": str(job.id)}

        db_job.status = "running"
        db.add(db_job)
        db.commit()

        for index, profile_id in enumerate(profile_ids):
            started = time.monotonic()
            try:
                assessment = service.assess_profile(db, profile_id)
                db.commit()
                successful_ids.append(str(assessment.id))
                db_job.processed = len(successful_ids)
            except Exception as exc:
                db.rollback()
                failed_profiles.append(
                    {"social_profile_id": str(profile_id), "error": str(exc)[:500]}
                )
                db_job.failed = len(failed_profiles)

            _update_job_metadata(
                db_job,
                assessment_ids=successful_ids,
                failed_profiles=failed_profiles,
            )
            db.add(db_job)
            db.commit()

            elapsed = time.monotonic() - started
            if interval > elapsed and index < len(profile_ids) - 1:
                time.sleep(interval - elapsed)

        db_job.status = "failed" if not successful_ids and failed_profiles else "completed"
        db_job.completed_at = datetime.now(timezone.utc)
        db_job.processed = len(successful_ids)
        db_job.failed = len(failed_profiles)
        _update_job_metadata(
            db_job,
            assessment_ids=successful_ids,
            failed_profiles=failed_profiles,
        )
        db.add(db_job)
        db.commit()

        return {
            "job_id": str(db_job.id),
            "assessment_ids": successful_ids,
            "failed_profiles": failed_profiles,
        }


def _score_job_results(
    previous_result: dict[str, Any] | None,
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    job_id = (previous_result or {}).get("job_id")
    if not job_id:
        return {"scored": 0, "job_id": None}

    scoring_service = ScoringService()
    with SessionLocal() as db:
        job = db.get(ProfilingJob, uuid.UUID(job_id))
        if not job:
            return {"scored": 0, "job_id": job_id}

        assessment_ids = [uuid.UUID(item) for item in (job.filters_used or {}).get("assessment_ids", [])]
        scored_ids: list[str] = []

        for assessment_id in assessment_ids:
            assessment = db.get(ProfileAssessment, assessment_id)
            if not assessment:
                continue
            lead_score = scoring_service.upsert_score(db, assessment, weights=weights)
            scored_ids.append(str(lead_score.id))

        _update_job_metadata(job, lead_score_ids=scored_ids, scoring_weights=weights or {})
        db.add(job)
        db.commit()
        return {"job_id": job_id, "scored": len(scored_ids), "lead_score_ids": scored_ids}


def _latest_lead_rows(
    filters: ProfilingFilters,
) -> list[tuple[LeadScore, ProfileAssessment, SocialProfile]]:
    with SessionLocal() as db:
        latest_subquery = (
            db.query(
                LeadScore.social_profile_id.label("social_profile_id"),
                func.max(LeadScore.created_at).label("latest_created_at"),
            )
            .group_by(LeadScore.social_profile_id)
            .subquery()
        )

        query = (
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

        if filters.platform:
            query = query.filter(SocialProfile.platform == filters.platform)
        if filters.cluster_id is not None:
            query = query.filter(SocialProfile.cluster_id == filters.cluster_id)
        if filters.location:
            query = query.filter(SocialProfile.location_inferred.ilike(f"%{filters.location}%"))
        if filters.min_followers is not None:
            query = query.filter(SocialProfile.follower_count >= filters.min_followers)

        return query.order_by(LeadScore.total_score.desc()).all()


@celery_app.task(
    bind=True,
    name="app.tasks.profiling_tasks.run_profiling_job",
)
def run_profiling_job(self: Task, job_id: str) -> dict[str, Any]:
    with SessionLocal() as db:
        job = db.get(ProfilingJob, uuid.UUID(job_id))
        if not job:
            return {"error": "job not found", "job_id": job_id}
    return _execute_profiling_job(job)


@celery_app.task(
    bind=True,
    name="app.tasks.profiling_tasks.profile_unassessed_task",
)
def profile_unassessed_task(self: Task) -> dict[str, Any]:
    filters = ProfilingFilters(unassessed_only=True)
    with SessionLocal() as db:
        profile_ids = select_profiles_for_profiling(
            db,
            filters,
            limit=settings.profiling_max_profiles_per_run,
        )
        job = ProfilingJob(
            id=uuid.uuid4(),
            status="pending" if profile_ids else "completed",
            total_profiles=len(profile_ids),
            filters_used={
                "filters": filters.model_dump(exclude_none=True),
                "profile_ids": [str(pid) for pid in profile_ids],
                "assessment_ids": [],
                "failed_profiles": [],
                "source": "nightly",
            },
            completed_at=None if profile_ids else datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    if not profile_ids:
        return {"job_id": str(job.id), "assessment_ids": [], "failed_profiles": []}
    return _execute_profiling_job(job)


@celery_app.task(
    bind=True,
    name="app.tasks.profiling_tasks.calculate_lead_scores",
)
def calculate_lead_scores(
    self: Task,
    previous_result: dict[str, Any] | None = None,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    return _score_job_results(previous_result, weights=weights)


@celery_app.task(
    bind=True,
    name="app.tasks.profiling_tasks.score_new_assessments_task",
)
def score_new_assessments_task(
    self: Task,
    previous_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _score_job_results(previous_result)


@celery_app.task(
    bind=True,
    name="app.tasks.profiling_tasks.generate_export",
)
def generate_export(
    self: Task,
    export_format: str = "csv",
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    export_service = ExportService()
    filter_model = ProfilingFilters.model_validate(filters or {})
    rows = _latest_lead_rows(filter_model)

    if export_format == "hubspot":
        data = export_service.build_hubspot_csv(rows)
        suffix = "hubspot"
    else:
        data = export_service.build_generic_csv(rows)
        suffix = "csv"

    file_key = f"profiling-{uuid.uuid4()}.{suffix}.csv"
    export_service.save_export(data, file_key)
    return {"file_key": file_key, "profile_count": len(rows), "format": export_format}
