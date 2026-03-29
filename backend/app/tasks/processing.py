"""Celery tasks for the Phase 2 NLP processing pipeline."""

from __future__ import annotations

import logging
import uuid

from celery import Task

from app.core.celery_app import celery_app
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.processing.process_profile_task",
    max_retries=2,
    default_retry_delay=120,
)
def process_profile_task(self: Task, profile_id: str) -> dict:
    """
    Run the full processing pipeline for a single social profile.
    Called automatically after collection and nightly via Celery Beat.
    """
    from app.processing.pipeline import process_profile as _run_pipeline

    db = SessionLocal()
    try:
        profile = db.query(SocialProfile).filter(SocialProfile.id == uuid.UUID(profile_id)).first()
        if not profile:
            log.warning("process_profile_task: profile %s not found", profile_id)
            return {"error": "not found"}

        result = _run_pipeline(profile, db)
        db.commit()

        log.info(
            "Processed @%s — %d posts, embedding=%s, location=%s",
            profile.username,
            result["posts_processed"],
            result["embedding_generated"],
            result["location_inferred"],
        )
        return result

    except Exception as exc:
        db.rollback()
        log.exception("process_profile_task failed for %s: %s", profile_id, exc)
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(name="app.tasks.processing.process_all_unprocessed")
def process_all_unprocessed() -> dict:
    """
    Dispatch process_profile_task for every profile that has unprocessed posts.
    Called nightly by Celery Beat, or manually via the admin API.
    """
    db = SessionLocal()
    try:
        profile_ids: list[str] = [
            str(row[0])
            for row in (
                db.query(SocialProfile.id)
                .join(Post, Post.profile_id == SocialProfile.id)
                .filter(Post.is_processed.is_(False))
                .distinct()
                .all()
            )
        ]

        for pid in profile_ids:
            process_profile_task.apply_async(args=[pid], queue="processing")

        log.info("process_all_unprocessed: dispatched %d profile tasks", len(profile_ids))
        return {"dispatched": len(profile_ids)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.processing.reembed_all_profiles")
def reembed_all_profiles() -> dict:
    """
    Force-recompute embeddings for all profiles (e.g. after a model upgrade).
    Admin-triggered only — not in the nightly schedule.
    """
    from app.processing.embeddings import embed_profile
    from app.processing.text_cleaner import clean_text, extract_hashtags

    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        profiles = db.query(SocialProfile).all()
        updated = 0

        for profile in profiles:
            posts = (
                db.query(Post)
                .filter(Post.profile_id == profile.id, Post.is_processed.is_(True))
                .limit(30)
                .all()
            )
            cleaned_tweets = [clean_text(p.content or "") for p in posts if p.content]
            hashtags: list[str] = []
            for p in posts:
                if p.content:
                    hashtags.extend(extract_hashtags(p.content))

            vec = embed_profile(profile.bio, cleaned_tweets, hashtags)
            if vec:
                profile.embedding = vec
                profile.embedding_updated_at = datetime.now(timezone.utc)
                db.add(profile)
                updated += 1

        db.commit()
        log.info("reembed_all_profiles: updated %d/%d profiles", updated, len(profiles))
        return {"total": len(profiles), "updated": updated}
    finally:
        db.close()
