"""Pydantic schemas for the Twitter/X user discovery feature."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ──────────────────────────────────────────────────────────

class KeywordExpansionRequest(BaseModel):
    seed_keywords: list[str] = Field(
        ..., min_length=1, description="One or more seed keywords, e.g. ['Fuel price pain']"
    )


class DiscoverySearchRequest(BaseModel):
    seed_keywords: list[str] = Field(
        ..., min_length=1, description="Original seed keywords from the user"
    )
    expanded_keywords: list[str] = Field(
        default_factory=list,
        description="LLM-expanded keywords (if empty, only seed keywords are used)",
    )
    location: str = Field(
        ..., min_length=1, description="Target location, e.g. 'Nigeria' or 'Lagos'"
    )
    date_from: date = Field(
        ..., description="Start of the search window"
    )
    date_to: date = Field(
        ..., description="End of the search window"
    )
    max_results: int = Field(
        default=200, ge=10, le=1000,
        description="Maximum tweets to scan across all keyword queries",
    )
    dummy_mode: bool = Field(
        default=False,
        description="When true, return simulated discovery results instead of calling Twitter.",
    )


class SaveDiscoveredUsersRequest(BaseModel):
    discovery_job_id: str = Field(..., description="ID of the discovery job")
    user_indices: list[int] = Field(
        ..., description="Indices of users in the discovery results to save",
    )


# ── Response schemas ─────────────────────────────────────────────────────────

class KeywordExpansionResponse(BaseModel):
    original: list[str]
    expanded: list[str]


class DiscoveredTweet(BaseModel):
    tweet_id: str
    content: str
    created_at: Optional[str] = None
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    post_type: str | None = None


class PublicContactInfo(BaseModel):
    emails: list[str] = Field(default_factory=list)
    phone_numbers: list[str] = Field(default_factory=list)
    social_handles: list[str] = Field(default_factory=list)
    urls: list[str] = Field(default_factory=list)


class DiscoveredUser(BaseModel):
    platform_user_id: str
    user_id: str | None = None
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location_raw: Optional[str] = None
    profile_image_url: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    tweet_count: int = 0
    location_match: bool = False
    relevance_score: float = 0.0
    matching_tweets: list[DiscoveredTweet] = Field(default_factory=list)
    date_joined_twitter: str | None = None
    last_10_tweets: list[DiscoveredTweet] = Field(default_factory=list)
    user_type: str | None = None
    public_contact_info: PublicContactInfo = Field(default_factory=PublicContactInfo)
    engagement_frequency_score: float = 0.0
    topic_relevance_score: float = 0.0
    conversation_influence_score: float = 0.0
    conversion_likelihood_score: float = 0.0
    high_value_score: float = 0.0
    high_value_band: str = "Low"
    hybrid_signals: list[str] = Field(default_factory=list)
    actionable_insights: list[str] = Field(default_factory=list)
    recommended_angle: str | None = None
    manual_followers_note: str | None = (
        "Follower list should be gathered manually when deeper network mapping is needed."
    )
    manual_followers_list: list[str] = Field(default_factory=list)
    manual_following_list: list[str] = Field(default_factory=list)
    manual_notes: str | None = None


class DiscoveryResponse(BaseModel):
    job_id: str
    status: str
    dummy_mode: bool = False
    seed_keywords: list[str]
    expanded_keywords: list[str]
    location: str
    users: list[DiscoveredUser]
    total_tweets_scanned: int
    total_users_found: int
    location_matched_count: int
    profiled_users_count: int = 0
    high_value_users_found: int = 0
    selected_micro_influencers: list[str] = Field(default_factory=list)


class DiscoveryJobSummary(BaseModel):
    id: str
    platform: str
    dummy_mode: bool = False
    seed_keywords: list[str]
    location: str
    status: str
    results_count: int
    tweets_scanned: int
    location_matched: int
    created_at: str


class DiscoveryHistoryResponse(BaseModel):
    jobs: list[DiscoveryJobSummary]


class SaveUsersResponse(BaseModel):
    saved_count: int
    profile_ids: list[str]


class DiscoveryUserManualEnrichmentRequest(BaseModel):
    followers_list: list[str] = Field(default_factory=list)
    following_list: list[str] = Field(default_factory=list)
    notes: str | None = None


class SharedFollowingsAnalyzeRequest(BaseModel):
    user_indices: list[int] = Field(default_factory=list)
    min_overlap: int = Field(default=2, ge=1, le=50)
    max_candidates: int = Field(default=25, ge=1, le=200)


class SharedFollowingCandidate(BaseModel):
    username: str
    display_name: str | None = None
    overlap_count: int
    followed_by_users: list[str] = Field(default_factory=list)
    discovered_user_index: int | None = None
    follower_count: int | None = None
    high_value_score: float | None = None
    high_value_band: str | None = None
    user_type: str | None = None
    micro_influencer_fit_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    selected: bool = False


class SharedFollowingsResponse(BaseModel):
    discovery_job_id: str
    analyzed_user_handles: list[str] = Field(default_factory=list)
    min_overlap: int
    total_candidates: int
    candidates: list[SharedFollowingCandidate] = Field(default_factory=list)


class SharedFollowingsSelectionRequest(BaseModel):
    usernames: list[str] = Field(default_factory=list)
