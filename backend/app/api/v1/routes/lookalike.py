from fastapi import APIRouter

from app.api.deps import CurrentAccount, DbDep
from app.intelligence.lookalike import find_lookalikes
from app.schemas.lookalike import LookalikeCandidate, LookalikeRequest, LookalikeResponse

router = APIRouter(prefix="/lookalike", tags=["lookalike"])


@router.post("", response_model=LookalikeResponse)
def search_lookalikes(request: LookalikeRequest, db: DbDep, _: CurrentAccount):
    seed_ids = [str(pid) for pid in request.seed_profile_ids] if request.seed_profile_ids else None

    candidates = find_lookalikes(
        db,
        seed_profile_ids=seed_ids,
        seed_cluster_id=request.seed_cluster_id,
        limit=request.limit,
        platform=request.platform,
        min_followers=request.min_followers,
        max_followers=request.max_followers,
        location=request.location,
    )

    return LookalikeResponse(
        seed_profile_count=len(seed_ids) if seed_ids else 0,
        seed_cluster_id=request.seed_cluster_id,
        results=[
            LookalikeCandidate(
                profile_id=c.profile_id,
                username=c.username,
                display_name=c.display_name,
                platform=c.platform,
                follower_count=c.follower_count,
                location_inferred=c.location_inferred,
                similarity_score=c.similarity_score,
            )
            for c in candidates
        ],
    )
