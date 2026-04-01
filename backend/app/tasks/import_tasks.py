"""Celery tasks for manual import and URL enrichment jobs."""

import logging
import uuid
from datetime import datetime, timezone

from celery import Task

from app.core.celery_app import celery_app
from app.db.models.collection_job import CollectionJob, JobStatus
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.import_tasks.run_csv_import_job",
    max_retries=2,
)
def run_csv_import_job(self: Task, job_id: str) -> dict:
    """
    Process a CSV/Excel import job.
    Reads raw file bytes from params, parses profiles, and upserts to DB.
    """
    db = SessionLocal()
    try:
        job = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
        if not job:
            return {"error": "job not found"}

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        params = job.params or {}
        file_content: bytes = bytes(params.get("file_content", b""))
        filename: str = params.get("filename", "upload.csv")
        default_platform: str = params.get("default_platform", "unknown")
        enrich_via_bot: bool = params.get("enrich_via_bot", False)

        from app.collectors.manual_import import ManualImportProcessor
        from app.tasks.processing import process_profile_task

        processor = ManualImportProcessor(use_proxy=enrich_via_bot)
        parsed_profiles = processor.parse_csv(file_content, filename, default_platform)

        # Optionally enrich profiles that have a profile_url
        if enrich_via_bot:
            urls_to_enrich = [
                p["_profile_url"]
                for p in parsed_profiles
                if p.get("_profile_url") and p.get("platform") == "unknown"
            ]
            if urls_to_enrich:
                enriched = processor.enrich_from_urls(urls_to_enrich[:50])  # cap at 50
                parsed_profiles.extend(enriched)

        count = 0
        profile_ids: list[str] = []
        for profile_data in parsed_profiles:
            try:
                profile = processor.upsert_profile(db, profile_data)
                profile_ids.append(str(profile.id))
                db.commit()
                count += 1
            except Exception as exc:
                log.warning("CSV import: failed to persist profile: %s", exc)
                db.rollback()

        # Auto-dispatch NLP processing
        for pid in profile_ids:
            process_profile_task.apply_async(args=[pid], queue="processing")

        job.status = JobStatus.completed
        job.profiles_collected = count
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        log.info("CSV import job %s completed — %d profiles", job_id, count)
        return {"job_id": job_id, "profiles_collected": count}

    except Exception as exc:
        log.exception("CSV import job %s failed: %s", job_id, exc)
        try:
            j = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
            if j:
                j.status = JobStatus.failed
                j.error_message = str(exc)[:2000]
                j.completed_at = datetime.now(timezone.utc)
                db.add(j)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.tasks.import_tasks.run_url_enrich_job",
    max_retries=2,
)
def run_url_enrich_job(self: Task, job_id: str) -> dict:
    """
    Enrich one or more profile URLs via bot scraping.
    URLs are stored in the job params as a list.
    """
    db = SessionLocal()
    try:
        job = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
        if not job:
            return {"error": "job not found"}

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        params = job.params or {}
        urls: list[str] = params.get("urls", [])
        use_proxy: bool = params.get("use_proxy", True)

        from app.collectors.manual_import import ManualImportProcessor
        from app.tasks.processing import process_profile_task

        processor = ManualImportProcessor(use_proxy=use_proxy)
        enriched_profiles = processor.enrich_from_urls(urls)

        count = 0
        profile_ids: list[str] = []
        for profile_data in enriched_profiles:
            try:
                profile = processor.upsert_profile(db, profile_data)
                profile_ids.append(str(profile.id))
                db.commit()
                count += 1
            except Exception as exc:
                log.warning("URL enrich: failed to persist profile: %s", exc)
                db.rollback()

        for pid in profile_ids:
            process_profile_task.apply_async(args=[pid], queue="processing")

        job.status = JobStatus.completed
        job.profiles_collected = count
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        log.info("URL enrich job %s completed — %d profiles", job_id, count)
        return {"job_id": job_id, "profiles_collected": count}

    except Exception as exc:
        log.exception("URL enrich job %s failed: %s", job_id, exc)
        try:
            j = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
            if j:
                j.status = JobStatus.failed
                j.error_message = str(exc)[:2000]
                j.completed_at = datetime.now(timezone.utc)
                db.add(j)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=30)
    finally:
        db.close()
