from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InterestOut(BaseModel):
    topic: str
    confidence: float

    model_config = {"from_attributes": True}


class PostSummaryOut(BaseModel):
    id: UUID
    content: str | None
    post_type: str | None
    likes: int | None
    reposts: int | None
    sentiment_score: float | None
    posted_at: datetime | None

    model_config = {"from_attributes": True}


class LinkedProfileOut(BaseModel):
    id: UUID
    platform: str
    username: str | None
    display_name: str | None
    follower_count: int | None

    model_config = {"from_attributes": True}


class ProfileOut(BaseModel):
    id: UUID
    platform: str
    platform_user_id: str
    username: str | None
    display_name: str | None
    bio: str | None
    profile_image_url: str | None
    location_inferred: str | None
    follower_count: int | None
    following_count: int | None
    tweet_count: int | None
    cluster_id: int | None
    affinity_score: float | None
    last_collected: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileDetailOut(ProfileOut):
    interests: list[InterestOut] = []
    recent_posts: list[PostSummaryOut] = []
    linked_profiles: list[LinkedProfileOut] = []

    @classmethod
    def from_orm_extended(cls, profile, interests, posts, linked_profiles):
        base = cls.model_validate(profile)
        base.interests = [InterestOut.model_validate(i) for i in interests]
        base.recent_posts = [PostSummaryOut.model_validate(p) for p in posts]
        base.linked_profiles = [LinkedProfileOut.model_validate(lp) for lp in linked_profiles]
        return base


class ProfileListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ProfileOut]
