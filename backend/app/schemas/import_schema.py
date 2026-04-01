"""Pydantic schemas for the manual import / URL enrichment endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class UrlEnrichRequest(BaseModel):
    url: str = Field(..., description="Full social media profile URL to scrape and enrich")


class BulkUrlEnrichRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1, max_length=200)
    use_proxy: bool = Field(default=True)


class ProxyAddRequest(BaseModel):
    url: str = Field(..., description="Proxy URL e.g. socks5://user:pass@host:port")
    carrier: str = Field(
        default="other",
        description="Carrier name: mtn | airtel | glo | 9mobile | residential | datacenter",
    )
    proxy_type: str = Field(default="mobile", description="mobile | residential | datacenter")


class SessionAddRequest(BaseModel):
    platform: str = Field(..., description="Platform: tiktok | linkedin | instagram | twitter | facebook")
    cookies: list[dict[str, Any]] = Field(..., description="Cookie list from Playwright context.cookies()")
    user_agent: str
    proxy_id: str | None = None
    account_age_days: int = Field(default=0, ge=0)


class ImportJobOut(BaseModel):
    id: UUID
    platform: str
    status: str
    params: dict[str, Any] | None
    celery_task_id: str | None
    profiles_collected: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ProxyStatsOut(BaseModel):
    total: int
    active: int
    failed: int
    by_carrier: dict[str, int]


class SessionStatsOut(BaseModel):
    total: int
    active: int
    by_platform: dict[str, int]


class ImportResultOut(BaseModel):
    profiles_imported: int
    profiles_failed: int
    job_id: str | None = None
    message: str = ""


class CsvImportParams(BaseModel):
    default_platform: str = Field(
        default="unknown",
        description="Default platform to assign when the CSV has no 'platform' column",
    )
    enrich_via_bot: bool = Field(
        default=False,
        description="If True, attempt bot-based enrichment for rows with a profile_url",
    )
