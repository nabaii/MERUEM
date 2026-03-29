import json

from fastapi import APIRouter
from sqlalchemy import func

from app.api.deps import CurrentAccount, DbDep
from app.core.cache import cache
from app.db.models.cluster import Cluster
from app.db.models.collection_job import CollectionJob, JobStatus
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile
from app.schemas.stats import PlatformCount, RecentJobOut, StatsOut

router = APIRouter(prefix="/stats", tags=["stats"])

_CACHE_KEY = "stats:global"
_CACHE_TTL = 60  # seconds


@router.get("", response_model=StatsOut)
def get_stats(db: DbDep, _: CurrentAccount):
    cached = cache.get(_CACHE_KEY)
    if cached:
        return StatsOut(**cached)
    total_profiles = db.query(SocialProfile).count()
    total_posts = db.query(Post).count()
    total_clusters = db.query(Cluster).filter(Cluster.member_count > 0).count()
    active_jobs = (
        db.query(CollectionJob)
        .filter(CollectionJob.status.in_([JobStatus.pending, JobStatus.running]))
        .count()
    )

    # Profiles grouped by platform
    platform_rows = (
        db.query(SocialProfile.platform, func.count(SocialProfile.id).label("cnt"))
        .group_by(SocialProfile.platform)
        .all()
    )
    profiles_by_platform = [
        PlatformCount(platform=r.platform, count=r.cnt) for r in platform_rows
    ]

    # Top 5 clusters by member count
    top_clusters_rows = (
        db.query(Cluster)
        .filter(Cluster.member_count > 0)
        .order_by(Cluster.member_count.desc())
        .limit(5)
        .all()
    )
    top_clusters = [
        {"id": c.id, "label": c.label, "member_count": c.member_count}
        for c in top_clusters_rows
    ]

    # Last 5 collection jobs
    recent_job_rows = (
        db.query(CollectionJob)
        .order_by(CollectionJob.created_at.desc())
        .limit(5)
        .all()
    )
    recent_jobs = [
        RecentJobOut(
            id=str(j.id),
            platform=j.platform,
            status=j.status.value,
            profiles_collected=j.profiles_collected,
            created_at=j.created_at,
        )
        for j in recent_job_rows
    ]

    result = StatsOut(
        total_profiles=total_profiles,
        total_posts=total_posts,
        total_clusters=total_clusters,
        active_jobs=active_jobs,
        profiles_by_platform=profiles_by_platform,
        top_clusters=top_clusters,
        recent_jobs=recent_jobs,
    )
    cache.set(_CACHE_KEY, result.model_dump(), ttl=_CACHE_TTL)
    return result
