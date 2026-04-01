from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProfilingFilters(BaseModel):
    cluster_id: int | None = None
    platform: str | None = None
    location: str | None = None
    min_followers: int | None = Field(default=None, ge=0)
    unassessed_only: bool = True


class ProfilingJobCreate(BaseModel):
    filters: ProfilingFilters = Field(default_factory=ProfilingFilters)


class AssessSingleRequest(BaseModel):
    social_profile_id: UUID
    force: bool = True


class ProfileMiniOut(BaseModel):
    id: UUID
    platform: str
    username: str | None
    display_name: str | None
    follower_count: int | None
    cluster_id: int | None

    model_config = {"from_attributes": True}


class AssessmentPayload(BaseModel):
    persona: str | None = None
    primary_interests: list[str] = Field(default_factory=list, max_length=5)
    secondary_interests: list[str] = Field(default_factory=list, max_length=3)
    sentiment_tone: str | None = None
    purchase_intent_score: int | None = Field(default=None, ge=1, le=10)
    influence_tier: str | None = None
    engagement_style: str | None = None
    psychographic_driver: str | None = None
    recommended_channel: str | None = None
    recommended_message_angle: str | None = None
    industry_fit: list[str] = Field(default_factory=list)
    confidence: str | None = None


class AssessmentOut(BaseModel):
    id: UUID
    social_profile_id: UUID
    unified_user_id: UUID | None
    persona: str | None
    primary_interests: list[str] | None
    secondary_interests: list[str] | None
    sentiment_tone: str | None
    purchase_intent_score: int | None
    influence_tier: str | None
    engagement_style: str | None
    psychographic_driver: str | None
    recommended_channel: str | None
    recommended_message_angle: str | None
    industry_fit: list[str] | None
    confidence: str | None
    model_used: str | None
    created_at: datetime
    profile: ProfileMiniOut | None = None

    model_config = {"from_attributes": True}


class AssessmentDetailOut(AssessmentOut):
    raw_llm_response: str | None


class AssessmentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AssessmentOut]


class LeadScoreOut(BaseModel):
    id: UUID
    social_profile_id: UUID
    assessment_id: UUID
    total_score: float
    score_breakdown: dict[str, Any] | None
    tier: str | None
    target_industries: list[str] | None
    created_at: datetime
    profile: ProfileMiniOut | None = None

    model_config = {"from_attributes": True}


class LeadScoreListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[LeadScoreOut]


class LeadScoreRecalculateRequest(BaseModel):
    weights: dict[str, float] | None = None


class LeadScoreRecalculateResponse(BaseModel):
    recalculated: int
    weights: dict[str, float]


class ProfilingJobOut(BaseModel):
    id: UUID
    status: str
    total_profiles: int
    processed: int
    failed: int
    filters_used: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ProfilingJobDetailOut(ProfilingJobOut):
    profile_ids: list[str] = Field(default_factory=list)
    assessment_ids: list[str] = Field(default_factory=list)
    failed_profiles: list[dict[str, Any]] = Field(default_factory=list)


class ProfilingStatsOut(BaseModel):
    total_assessed: int
    persona_distribution: dict[str, int]
    avg_purchase_intent: float | None
    tier_breakdown: dict[str, int]
    top_industries: dict[str, int]
