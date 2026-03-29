"""Celery tasks for social media data collection."""

import logging
import uuid
from datetime import datetime, timezone

from celery import Task

from app.core.celery_app import celery_app
from app.db.models.collection_job import CollectionJob, JobStatus
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.collection.run_collection_job", max_retries=3)
def run_collection_job(self: Task, job_id: str) -> dict:
    """
    Execute a collection job.
    Reads params from CollectionJob row, runs the appropriate collector,
    and updates job status on completion or failure.
    """
    db = SessionLocal()
    try:
        job = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
        if not job:
            log.error("Collection job %s not found", job_id)
            return {"error": "job not found"}

        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        if job.platform == "twitter":
            count = _run_twitter_job(job, db)
        elif job.platform == "instagram":
            count = _run_instagram_job(job, db)
        elif job.platform == "facebook":
            count = _run_facebook_job(job, db)
        else:
            raise NotImplementedError(f"Collector for '{job.platform}' not yet implemented")

        job.status = JobStatus.completed
        job.profiles_collected = count
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        log.info("Job %s completed — %d profiles", job_id, count)
        return {"job_id": job_id, "profiles_collected": count}

    except Exception as exc:
        log.exception("Job %s failed: %s", job_id, exc)
        try:
            job = db.query(CollectionJob).filter(CollectionJob.id == uuid.UUID(job_id)).first()
            if job:
                job.status = JobStatus.failed
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


def _run_twitter_job(job: CollectionJob, db) -> int:
    """Run Twitter collection and persist results. Returns profile count."""
    from app.collectors.twitter import TwitterCollector

    collector = TwitterCollector()
    params = job.params or {}
    seed_usernames: list[str] = params.get("seed_usernames", [])
    max_profiles: int = params.get("max_profiles", 1000)
    tweets_per_user: int = params.get("tweets_per_user", 50)

    if not seed_usernames:
        log.warning("No seed_usernames in job params — nothing to collect")
        return 0

    parsed_profiles = collector.collect_from_usernames(
        seed_usernames=seed_usernames,
        max_profiles=max_profiles,
        tweets_per_user=tweets_per_user,
    )

    from app.tasks.processing import process_profile_task

    count = 0
    profile_ids: list[str] = []
    for parsed in parsed_profiles:
        try:
            profile = collector.upsert_profile(db, parsed)
            profile_ids.append(str(profile.id))
            count += 1
        except Exception as exc:
            log.warning("Failed to persist profile %s: %s", parsed.get("username"), exc)
            db.rollback()
        else:
            db.commit()

    # Auto-dispatch NLP processing for each newly collected profile
    for pid in profile_ids:
        process_profile_task.apply_async(args=[pid], queue="processing")
    log.info("Auto-dispatched processing for %d profiles", len(profile_ids))

    return count


def _run_instagram_job(job: CollectionJob, db) -> int:
    """Run Instagram collection and persist results. Returns profile count."""
    from app.collectors.instagram import InstagramCollector
    from app.tasks.processing import process_profile_task

    collector = InstagramCollector()
    params = job.params or {}
    seed_usernames: list[str] = params.get("seed_usernames", [])
    seed_user_ids: list[str] = params.get("seed_user_ids", [])
    max_profiles: int = params.get("max_profiles", 500)
    media_per_user: int = params.get("media_per_user", 30)

    if not seed_usernames and not seed_user_ids:
        log.warning("No seed_usernames or seed_user_ids in Instagram job params")
        return 0

    if seed_user_ids:
        parsed_profiles = collector.collect_from_user_ids(
            seed_user_ids=seed_user_ids,
            max_profiles=max_profiles,
            media_per_user=media_per_user,
        )
    else:
        parsed_profiles = collector.collect_from_usernames(
            seed_usernames=seed_usernames,
            max_profiles=max_profiles,
            media_per_user=media_per_user,
        )

    count = 0
    profile_ids: list[str] = []
    for parsed in parsed_profiles:
        try:
            profile = collector.upsert_profile(db, parsed)
            profile_ids.append(str(profile.id))
            count += 1
        except Exception as exc:
            log.warning("Failed to persist IG profile %s: %s", parsed.get("username"), exc)
            db.rollback()
        else:
            db.commit()

    for pid in profile_ids:
        process_profile_task.apply_async(args=[pid], queue="processing")
    log.info("Auto-dispatched processing for %d IG profiles", len(profile_ids))

    return count


def _run_facebook_job(job: CollectionJob, db) -> int:
    """Run Facebook collection and persist results. Returns profile count."""
    from app.collectors.facebook import FacebookCollector
    from app.tasks.processing import process_profile_task

    collector = FacebookCollector()
    params = job.params or {}
    seed_usernames: list[str] = params.get("seed_usernames", [])
    seed_page_ids: list[str] = params.get("seed_page_ids", [])
    max_profiles: int = params.get("max_profiles", 500)
    posts_per_page: int = params.get("posts_per_page", 30)

    if not seed_usernames and not seed_page_ids:
        log.warning("No seed_usernames or seed_page_ids in Facebook job params")
        return 0

    if seed_page_ids:
        parsed_profiles = collector.collect_from_page_ids(
            seed_page_ids=seed_page_ids,
            max_profiles=max_profiles,
            posts_per_page=posts_per_page,
        )
    else:
        parsed_profiles = collector.collect_from_usernames(
            seed_usernames=seed_usernames,
            max_profiles=max_profiles,
            posts_per_page=posts_per_page,
        )

    count = 0
    profile_ids: list[str] = []
    for parsed in parsed_profiles:
        try:
            profile = collector.upsert_profile(db, parsed)
            profile_ids.append(str(profile.id))
            count += 1
        except Exception as exc:
            log.warning("Failed to persist FB profile %s: %s", parsed.get("username"), exc)
            db.rollback()
        else:
            db.commit()

    for pid in profile_ids:
        process_profile_task.apply_async(args=[pid], queue="processing")
    log.info("Auto-dispatched processing for %d FB profiles", len(profile_ids))

    return count


@celery_app.task(name="app.tasks.collection.run_scheduled_collection")
def run_scheduled_collection(platform: str) -> None:
    """
    Celery Beat entry point — creates a CollectionJob and dispatches it.
    Seed usernames should be configured per deployment.
    """
    from app.core.config import settings

    db = SessionLocal()
    try:
        job = CollectionJob(
            id=uuid.uuid4(),
            platform=platform,
            params={
                "seed_usernames": [],  # Configure via env/admin panel in Phase 4
                "max_profiles": 1000,
            },
        )
        db.add(job)
        db.commit()
        run_collection_job.apply_async(args=[str(job.id)], queue="collection")
        log.info("Scheduled %s collection dispatched — job %s", platform, job.id)
    finally:
        db.close()
