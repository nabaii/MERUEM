from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.db.models.campaign import CampaignStatus
from app.db.models.campaign_export import ExportFormat, ExportStatus


# ── Campaign schemas ──────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    filters: Optional[dict[str, Any]] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    filters: Optional[dict[str, Any]] = None


class CampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    owner_id: Optional[uuid.UUID]
    status: CampaignStatus
    filters: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    audience_count: int = 0

    model_config = {"from_attributes": True}


class CampaignDetailOut(CampaignOut):
    exports: list["CampaignExportOut"] = []


# ── Export schemas ────────────────────────────────────────────────────────────

class CampaignExportOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    format: ExportFormat
    profile_count: Optional[int]
    status: ExportStatus
    file_key: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportCreateRequest(BaseModel):
    format: ExportFormat


# ── Reach estimate ────────────────────────────────────────────────────────────

class ReachEstimateOut(BaseModel):
    estimated_profiles: int
    filters_applied: dict[str, Any]
