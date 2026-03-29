from datetime import datetime

from pydantic import BaseModel


class PlatformCount(BaseModel):
    platform: str
    count: int


class RecentJobOut(BaseModel):
    id: str
    platform: str
    status: str
    profiles_collected: int
    created_at: datetime


class StatsOut(BaseModel):
    total_profiles: int
    total_posts: int
    total_clusters: int
    active_jobs: int
    profiles_by_platform: list[PlatformCount]
    top_clusters: list[dict]       # id, label, member_count
    recent_jobs: list[RecentJobOut]
