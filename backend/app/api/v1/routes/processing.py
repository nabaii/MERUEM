"""Admin endpoints for triggering and monitoring the NLP processing pipeline."""

from fastapi import APIRouter
from sqlalchemy import func

from app.api.deps import AdminAccount, CurrentAccount, DbDep
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

router = APIRouter(prefix="/processing", tags=["processing"])


@router.post("/trigger", summary="Trigger NLP processing for all unprocessed profiles")
def trigger_processing(_: AdminAccount):
    """
    Dispatch process_all_unprocessed as an async Celery task.
    Returns immediately — check /processing/status to track progress.
    Admin only.
    """
    from app.tasks.processing import process_all_unprocessed

    task = process_all_unprocessed.apply_async(queue="processing")
    return {"queued": True, "task_id": task.id}


@router.post("/trigger/{profile_id}", summary="Trigger NLP processing for a single profile")
def trigger_single(profile_id: str, _: AdminAccount):
    """Reprocess a specific profile (useful for debugging). Admin only."""
    from app.tasks.processing import process_profile_task

    task = process_profile_task.apply_async(args=[profile_id], queue="processing")
    return {"queued": True, "profile_id": profile_id, "task_id": task.id}


@router.get("/status", summary="Processing pipeline status overview")
def processing_status(_: CurrentAccount, db: DbDep):
    """Return high-level counts on pipeline progress."""
    total_profiles = db.query(func.count(SocialProfile.id)).scalar()
    profiles_with_embedding = db.query(func.count(SocialProfile.id)).filter(
        SocialProfile.embedding.is_not(None)
    ).scalar()
    profiles_with_location = db.query(func.count(SocialProfile.id)).filter(
        SocialProfile.location_inferred.is_not(None)
    ).scalar()

    total_posts = db.query(func.count(Post.id)).scalar()
    processed_posts = db.query(func.count(Post.id)).filter(Post.is_processed.is_(True)).scalar()
    unprocessed_posts = total_posts - processed_posts

    return {
        "profiles": {
            "total": total_profiles,
            "with_embedding": profiles_with_embedding,
            "with_location": profiles_with_location,
            "embedding_coverage_pct": round(
                (profiles_with_embedding / total_profiles * 100) if total_profiles else 0, 1
            ),
            "location_coverage_pct": round(
                (profiles_with_location / total_profiles * 100) if total_profiles else 0, 1
            ),
        },
        "posts": {
            "total": total_posts,
            "processed": processed_posts,
            "unprocessed": unprocessed_posts,
        },
    }
