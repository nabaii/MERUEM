from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class LookalikeRequest(BaseModel):
    seed_profile_ids: list[UUID] | None = None
    seed_cluster_id: int | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    platform: str | None = None
    min_followers: int | None = Field(default=None, ge=0)
    max_followers: int | None = Field(default=None, ge=0)
    location: str | None = None

    @model_validator(mode="after")
    def require_seed(self) -> "LookalikeRequest":
        if not self.seed_profile_ids and self.seed_cluster_id is None:
            raise ValueError("Provide seed_profile_ids or seed_cluster_id")
        return self


class LookalikeCandidate(BaseModel):
    profile_id: str
    username: str | None
    display_name: str | None
    platform: str
    follower_count: int | None
    location_inferred: str | None
    similarity_score: float


class LookalikeResponse(BaseModel):
    seed_profile_count: int
    seed_cluster_id: int | None
    results: list[LookalikeCandidate]
