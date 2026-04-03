import logging
import uuid
import asgiref.sync

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.post import Post
from app.db.models.tiktok import TiktokMetricSnapshot
from app.collectors.tiktok_api import TikTokBusinessAPI

logger = logging.getLogger(__name__)

@celery_app.task(name="fetch_tiktok_video_metrics")
def fetch_tiktok_video_metrics(post_id: str):
    """
    Celery task to fetch TikTok metrics for a specific post.
    Creates a snapshot in the database.
    """
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post or post.platform_post_id is None:
            logger.error(f"Post {post_id} not found or missing platform_id")
            return
            
        collector = TikTokBusinessAPI()
        metrics = asgiref.sync.async_to_sync(collector.fetch_video_metrics)(post.platform_post_id)
        
        if metrics:
            snapshot = TiktokMetricSnapshot(
                post_id=post.id,
                views=metrics["views"],
                likes=metrics["likes"],
                comments=metrics["comments"],
                shares=metrics["shares"],
                saves=metrics["saves"],
                avg_watch_time=metrics["avg_watch_time"],
                play_count=metrics["play_count"]
            )
            # Basic velocity score calculation for Sprint 1 (v1)
            # V = (5 * Loops) + (4 * Completions) + (3 * Shares) + (3 * Saves) + (2 * Comments) + (1 * Likes)
            # Simplified loops = play_count - reach (views)
            loops = max(0, snapshot.play_count - snapshot.views)
            v_score_raw = (5 * loops) + (3 * snapshot.shares) + (3 * snapshot.saves) + (2 * snapshot.comments) + (1 * snapshot.likes)
            
            db.add(snapshot)
            db.commit()
            logger.info(f"Saved metric snapshot for post {post_id}")
            # The TiktokVelocityScore logging will be added in further sprints
            
    except Exception as e:
        logger.error(f"Error fetching metrics for {post_id}: {str(e)}")
    finally:
        db.close()
