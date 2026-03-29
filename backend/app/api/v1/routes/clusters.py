from fastapi import APIRouter, HTTPException, Query

from app.api.deps import CurrentAccount, DbDep
from app.db.models.cluster import Cluster
from app.db.models.social_profile import SocialProfile
from app.schemas.clusters import (
    ClusterListResponse,
    ClusterOut,
    ClusterProfileOut,
    ClusterProfilesResponse,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.get("", response_model=ClusterListResponse)
def list_clusters(db: DbDep, _: CurrentAccount):
    clusters = db.query(Cluster).order_by(Cluster.member_count.desc()).all()
    return ClusterListResponse(
        total=len(clusters),
        items=[ClusterOut.model_validate(c) for c in clusters],
    )


@router.get("/{cluster_id}", response_model=ClusterOut)
def get_cluster(cluster_id: int, db: DbDep, _: CurrentAccount):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return ClusterOut.model_validate(cluster)


@router.get("/{cluster_id}/profiles", response_model=ClusterProfilesResponse)
def list_cluster_profiles(
    cluster_id: int,
    db: DbDep,
    _: CurrentAccount,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    cluster = db.query(Cluster).filter(Cluster.id == cluster_id).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    total = (
        db.query(SocialProfile)
        .filter(SocialProfile.cluster_id == cluster_id)
        .count()
    )
    profiles = (
        db.query(SocialProfile)
        .filter(SocialProfile.cluster_id == cluster_id)
        .order_by(SocialProfile.affinity_score.desc().nulls_last())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ClusterProfilesResponse(
        cluster_id=cluster_id,
        total=total,
        limit=limit,
        offset=offset,
        items=[ClusterProfileOut.model_validate(p) for p in profiles],
    )
