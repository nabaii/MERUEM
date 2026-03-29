from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import AdminAccount, CurrentAccount, DbDep
from app.db.models.profile_link import LinkStatus, ProfileLink
from app.db.models.social_profile import SocialProfile
from app.schemas.identity import (
    ProfileLinkListResponse,
    ProfileLinkOut,
    ProfileSummary,
    ReviewAction,
)

router = APIRouter(prefix="/identity-links", tags=["identity"])


def _to_out(link: ProfileLink, db) -> ProfileLinkOut:
    src = db.query(SocialProfile).filter(SocialProfile.id == link.source_profile_id).first()
    tgt = db.query(SocialProfile).filter(SocialProfile.id == link.target_profile_id).first()
    return ProfileLinkOut(
        id=link.id,
        source_profile=ProfileSummary.model_validate(src) if src else ProfileSummary(
            id=link.source_profile_id, platform="unknown", username=None, display_name=None
        ),
        target_profile=ProfileSummary.model_validate(tgt) if tgt else ProfileSummary(
            id=link.target_profile_id, platform="unknown", username=None, display_name=None
        ),
        confidence=link.confidence,
        match_method=link.match_method,
        status=link.status.value if hasattr(link.status, "value") else link.status,
        created_at=link.created_at,
    )


@router.get("", response_model=ProfileLinkListResponse)
def list_links(
    db: DbDep,
    _: CurrentAccount,
    status: str | None = Query(default=None, pattern="^(pending|confirmed|rejected)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(ProfileLink)
    if status:
        query = query.filter(ProfileLink.status == status)

    total = query.count()
    links = query.order_by(ProfileLink.confidence.desc()).offset(offset).limit(limit).all()

    return ProfileLinkListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_out(link, db) for link in links],
    )


@router.post("/{link_id}/review", response_model=ProfileLinkOut)
def review_link(
    link_id: UUID,
    body: ReviewAction,
    db: DbDep,
    account: AdminAccount,
):
    """Confirm or reject a pending identity match. Admin only."""
    if body.action not in ("confirm", "reject"):
        raise HTTPException(status_code=422, detail="action must be 'confirm' or 'reject'")

    link = db.query(ProfileLink).filter(ProfileLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    if link.status != LinkStatus.pending:
        raise HTTPException(status_code=409, detail="Link is not pending")

    if body.action == "confirm":
        link.status = LinkStatus.confirmed
        link.reviewed_by = account.id

        # If no unified_user exists yet, create one
        if link.unified_user_id is None:
            from app.db.models.unified_user import UnifiedUser
            import uuid as _uuid
            src = db.query(SocialProfile).filter(SocialProfile.id == link.source_profile_id).first()
            uu = UnifiedUser(id=_uuid.uuid4(), canonical_name=src.display_name if src else None)
            db.add(uu)
            db.flush()
            link.unified_user_id = uu.id

            src_profile = db.query(SocialProfile).filter(SocialProfile.id == link.source_profile_id).first()
            tgt_profile = db.query(SocialProfile).filter(SocialProfile.id == link.target_profile_id).first()
            if src_profile and not src_profile.unified_user_id:
                src_profile.unified_user_id = uu.id
            if tgt_profile and not tgt_profile.unified_user_id:
                tgt_profile.unified_user_id = uu.id
    else:
        link.status = LinkStatus.rejected
        link.reviewed_by = account.id

    db.commit()
    db.refresh(link)
    return _to_out(link, db)
