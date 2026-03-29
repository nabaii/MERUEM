from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "meruem",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.collection",
        "app.tasks.processing",
        "app.tasks.intelligence",
        "app.tasks.campaigns",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.collection.*": {"queue": "collection"},
        "app.tasks.processing.*": {"queue": "processing"},
        "app.tasks.intelligence.*": {"queue": "intelligence"},
        "app.tasks.campaigns.*": {"queue": "default"},
    },
    beat_schedule={
        # Hourly Twitter collection — enabled once Twitter creds are configured
        "hourly-twitter-collection": {
            "task": "app.tasks.collection.run_scheduled_collection",
            "schedule": crontab(minute=0),
            "args": ["twitter"],
        },
        # Hourly Instagram collection — enabled once Instagram creds are configured
        "hourly-instagram-collection": {
            "task": "app.tasks.collection.run_scheduled_collection",
            "schedule": crontab(minute=30),  # stagger 30 min after Twitter
            "args": ["instagram"],
        },
        # Nightly NLP processing pass at 02:00 UTC
        "nightly-nlp-processing": {
            "task": "app.tasks.processing.process_all_unprocessed",
            "schedule": crontab(hour=2, minute=0),
        },
        # Nightly ML intelligence pipeline at 03:00 UTC (after processing)
        "nightly-intelligence-pipeline": {
            "task": "app.tasks.intelligence.run_nightly_intelligence_pipeline",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)
