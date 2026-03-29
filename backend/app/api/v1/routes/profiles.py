from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentAccount, DbDep
from app.db.models.post import Post
from app.db.models.profile_interest import ProfileInterest
from app.db.models.profile_link import LinkStatus, ProfileLink
from app.db.models.social_profile import SocialProfile
from app.schemas.profiles import ProfileDetailOut, ProfileListResponse, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=ProfileListResponse)
def list_profiles(
    _: CurrentAccount,
    db: DbDep,
    q: str | None = Query(default=None, description="Search username or display name"),
    platform: str | None = Query(default=None),
    cluster_id: int | None = Query(default=None),
    interest: str | None = Query(default=None, description="Filter by topic tag"),
    location: str | None = Query(default=None),
    min_followers: int | None = Query(default=None, ge=0),
    max_followers: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = db.query(SocialProfile)

    if q:
        like = f"%{q}%"
        query = query.filter(
            SocialProfile.username.ilike(like) | SocialProfile.display_name.ilike(like)
        )
    if platform:
        query = query.filter(SocialProfile.platform == platform)
    if cluster_id is not None:
        query = query.filter(SocialProfile.cluster_id == cluster_id)
    if location:
        query = query.filter(SocialProfile.location_inferred.ilike(f"%{location}%"))
    if min_followers is not None:
        query = query.filter(SocialProfile.follower_count >= min_followers)
    if max_followers is not None:
        query = query.filter(SocialProfile.follower_count <= max_followers)
    if interest:
        query = query.join(ProfileInterest).filter(ProfileInterest.topic == interest)

    total = query.count()
    items = query.order_by(SocialProfile.follower_count.desc().nulls_last()).offset(offset).limit(limit).all()
    return ProfileListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{profile_id}", response_model=ProfileDetailOut)
def get_profile(profile_id: UUID, _: CurrentAccount, db: DbDep):
    profile = db.query(SocialProfile).filter(SocialProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    interests = (
        db.query(ProfileInterest)
        .filter(ProfileInterest.profile_id == profile_id)
        .order_by(ProfileInterest.confidence.desc())
        .all()
    )

    recent_posts = (
        db.query(Post)
        .filter(Post.profile_id == profile_id)
        .order_by(Post.posted_at.desc())
        .limit(20)
        .all()
    )

    # Confirmed cross-platform links
    links = (
        db.query(ProfileLink)
        .filter(
            (ProfileLink.source_profile_id == profile_id)
            | (ProfileLink.target_profile_id == profile_id),
            ProfileLink.status == LinkStatus.confirmed,
        )
        .all()
    )

    linked_ids: list[UUID] = []
    for lnk in links:
        other = lnk.target_profile_id if lnk.source_profile_id == profile_id else lnk.source_profile_id
        linked_ids.append(other)

    linked_profiles = (
        db.query(SocialProfile).filter(SocialProfile.id.in_(linked_ids)).all()
        if linked_ids
        else []
    )

    return ProfileDetailOut.from_orm_extended(profile, interests, recent_posts, linked_profiles)
