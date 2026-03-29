from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
import io

from app.api.deps import CurrentAccount, DbDep
from app.db.models.campaign import Campaign, CampaignStatus
from app.db.models.campaign_audience import CampaignAudience
from app.db.models.campaign_export import CampaignExport, ExportStatus
from app.db.models.social_profile import SocialProfile
from app.notifications.in_app import notify_campaign_activated
from app.schemas.campaigns import (
    CampaignCreate,
    CampaignDetailOut,
    CampaignExportOut,
    CampaignOut,
    CampaignUpdate,
    ExportCreateRequest,
    ReachEstimateOut,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_campaign_or_404(db, campaign_id: uuid.UUID, account_id: uuid.UUID) -> Campaign:
    c = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.owner_id == account_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return c


def _audience_count(db, campaign_id: uuid.UUID) -> int:
    return db.query(CampaignAudience).filter(
        CampaignAudience.campaign_id == campaign_id
    ).count()


def _campaign_out(db, c: Campaign) -> CampaignOut:
    out = CampaignOut.model_validate(c)
    out.audience_count = _audience_count(db, c.id)
    return out


def _campaign_detail_out(db, c: Campaign) -> CampaignDetailOut:
    out = CampaignDetailOut.model_validate(c)
    out.audience_count = _audience_count(db, c.id)
    out.exports = [CampaignExportOut.model_validate(e) for e in c.exports]
    return out


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    db: DbDep,
    current: CurrentAccount,
    status: Optional[CampaignStatus] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Campaign).filter(Campaign.owner_id == current.id)
    if status:
        q = q.filter(Campaign.status == status)
    campaigns = q.order_by(Campaign.created_at.desc()).offset(offset).limit(limit).all()
    return [_campaign_out(db, c) for c in campaigns]


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignCreate, db: DbDep, current: CurrentAccount):
    c = Campaign(name=body.name, owner_id=current.id, filters=body.filters or {})
    db.add(c)
    db.commit()
    db.refresh(c)
    return _campaign_out(db, c)


@router.get("/{campaign_id}", response_model=CampaignDetailOut)
def get_campaign(campaign_id: uuid.UUID, db: DbDep, current: CurrentAccount):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    return _campaign_detail_out(db, c)


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: uuid.UUID,
    body: CampaignUpdate,
    db: DbDep,
    current: CurrentAccount,
):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    if c.status != CampaignStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft campaigns can be edited")
    if body.name is not None:
        c.name = body.name
    if body.filters is not None:
        c.filters = body.filters
    db.commit()
    db.refresh(c)
    return _campaign_out(db, c)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: uuid.UUID, db: DbDep, current: CurrentAccount):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    db.delete(c)
    db.commit()
    return Response(status_code=204)


# ── Audience management ───────────────────────────────────────────────────────

@router.post("/{campaign_id}/audiences", status_code=204)
def add_profiles_to_campaign(
    campaign_id: uuid.UUID,
    profile_ids: list[uuid.UUID],
    db: DbDep,
    current: CurrentAccount,
):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    existing = {
        row.profile_id
        for row in db.query(CampaignAudience).filter(
            CampaignAudience.campaign_id == campaign_id
        ).all()
    }
    for pid in profile_ids:
        if pid not in existing:
            db.add(CampaignAudience(campaign_id=c.id, profile_id=pid))
    db.commit()
    return Response(status_code=204)


@router.delete("/{campaign_id}/audiences", status_code=204)
def remove_profiles_from_campaign(
    campaign_id: uuid.UUID,
    profile_ids: list[uuid.UUID],
    db: DbDep,
    current: CurrentAccount,
):
    _get_campaign_or_404(db, campaign_id, current.id)
    db.query(CampaignAudience).filter(
        CampaignAudience.campaign_id == campaign_id,
        CampaignAudience.profile_id.in_(profile_ids),
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=204)


# ── Activate ──────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/activate", response_model=CampaignOut)
def activate_campaign(campaign_id: uuid.UUID, db: DbDep, current: CurrentAccount):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    if c.status != CampaignStatus.draft:
        raise HTTPException(status_code=400, detail="Campaign is not in draft status")
    if _audience_count(db, c.id) == 0:
        raise HTTPException(status_code=400, detail="Campaign has no audience profiles")
    c.status = CampaignStatus.active
    db.commit()
    db.refresh(c)
    notify_campaign_activated(db, current.id, c.name, c.id)
    return _campaign_out(db, c)


# ── Reach estimate ────────────────────────────────────────────────────────────

@router.get("/reach-estimate", response_model=ReachEstimateOut)
def reach_estimate(
    db: DbDep,
    current: CurrentAccount,
    platform: Optional[str] = None,
    cluster_id: Optional[int] = None,
    location: Optional[str] = None,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
):
    q = db.query(SocialProfile)
    filters: dict = {}
    if platform:
        q = q.filter(SocialProfile.platform == platform)
        filters["platform"] = platform
    if cluster_id is not None:
        q = q.filter(SocialProfile.cluster_id == cluster_id)
        filters["cluster_id"] = cluster_id
    if location:
        q = q.filter(SocialProfile.location.ilike(f"%{location}%"))
        filters["location"] = location
    if min_followers is not None:
        q = q.filter(SocialProfile.follower_count >= min_followers)
        filters["min_followers"] = min_followers
    if max_followers is not None:
        q = q.filter(SocialProfile.follower_count <= max_followers)
        filters["max_followers"] = max_followers
    return ReachEstimateOut(estimated_profiles=q.count(), filters_applied=filters)


# ── Export ────────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/exports", response_model=CampaignExportOut, status_code=201)
def create_export(
    campaign_id: uuid.UUID,
    body: ExportCreateRequest,
    db: DbDep,
    current: CurrentAccount,
):
    from app.tasks.campaigns import generate_export_task

    c = _get_campaign_or_404(db, campaign_id, current.id)
    if c.status == CampaignStatus.draft:
        raise HTTPException(status_code=400, detail="Activate the campaign before exporting")

    export = CampaignExport(
        campaign_id=c.id,
        format=body.format,
        created_by=current.id,
    )
    db.add(export)
    db.commit()
    db.refresh(export)

    generate_export_task.delay(str(export.id))
    return CampaignExportOut.model_validate(export)


@router.get("/{campaign_id}/exports", response_model=list[CampaignExportOut])
def list_exports(campaign_id: uuid.UUID, db: DbDep, current: CurrentAccount):
    c = _get_campaign_or_404(db, campaign_id, current.id)
    exports = (
        db.query(CampaignExport)
        .filter(CampaignExport.campaign_id == c.id)
        .order_by(CampaignExport.created_at.desc())
        .all()
    )
    return [CampaignExportOut.model_validate(e) for e in exports]


@router.get("/{campaign_id}/exports/{export_id}/download")
def download_export(
    campaign_id: uuid.UUID,
    export_id: uuid.UUID,
    db: DbDep,
    current: CurrentAccount,
):
    from app.export.csv_generator import read_export_file

    _get_campaign_or_404(db, campaign_id, current.id)
    export = db.query(CampaignExport).filter(
        CampaignExport.id == export_id,
        CampaignExport.campaign_id == campaign_id,
    ).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != ExportStatus.ready:
        raise HTTPException(status_code=409, detail=f"Export is {export.status.value}")

    try:
        data = read_export_file(export.file_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Export file not found on disk")

    filename = export.file_key.split("/")[-1]
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
