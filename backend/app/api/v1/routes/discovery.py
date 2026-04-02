"""API routes for Twitter/X user discovery."""

import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.discovery_job import DiscoveryJob, DiscoveryStatus
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile
from app.schemas.discovery import (
    DiscoveredUser,
    DiscoveryUserManualEnrichmentRequest,
    DiscoveryHistoryResponse,
    DiscoveryJobSummary,
    DiscoverySearchRequest,
    DiscoveryResponse,
    KeywordExpansionRequest,
    KeywordExpansionResponse,
    SharedFollowingsAnalyzeRequest,
    SharedFollowingsResponse,
    SharedFollowingsSelectionRequest,
    SaveDiscoveredUsersRequest,
    SaveUsersResponse,
)
from app.services.discovery_export_service import DiscoveryExportService
from app.services.keyword_expander import expand_keywords
from app.services.twitter_discovery import TwitterDiscoveryService
from app.services.twitter_list_workbench import analyze_shared_followings, clean_manual_handle_list

log = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _get_job_or_404(job_id: str, db: Session) -> DiscoveryJob:
    try:
        parsed = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Discovery job not found") from exc

    job = db.query(DiscoveryJob).filter_by(id=parsed).first()
    if not job:
        raise HTTPException(status_code=404, detail="Discovery job not found")
    return job


def _get_job_users(job: DiscoveryJob) -> list[dict]:
    if not job.results_data or "users" not in job.results_data:
        raise HTTPException(status_code=400, detail="No results data in this job")
    return list(job.results_data.get("users") or [])


@router.post("/expand-keywords", response_model=KeywordExpansionResponse)
async def expand_keywords_endpoint(body: KeywordExpansionRequest):
    """Expand seed keywords using an LLM to generate related search phrases.

    The user can review and edit the expanded keywords before searching.
    """
    expanded = await expand_keywords(body.seed_keywords)
    return KeywordExpansionResponse(
        original=body.seed_keywords,
        expanded=expanded,
    )


@router.post("/search", response_model=DiscoveryResponse)
def search_twitter(body: DiscoverySearchRequest, db: Session = Depends(get_db)):
    """Run a Twitter discovery search with the given keywords and location.

    Combines seed + expanded keywords, searches Twitter, and returns
    users prioritised by location match and engagement relevance.
    """
    # Combine all keywords (seed + expanded)
    all_keywords = list(set(body.seed_keywords + body.expanded_keywords))
    if not all_keywords:
        raise HTTPException(status_code=400, detail="At least one keyword is required")

    # Create a discovery job record
    job = DiscoveryJob(
        id=uuid.uuid4(),
        platform="twitter",
        seed_keywords=body.seed_keywords,
        expanded_keywords=body.expanded_keywords,
        location=body.location,
        date_from=datetime.combine(body.date_from, datetime.min.time()).replace(tzinfo=timezone.utc),
        date_to=datetime.combine(body.date_to, datetime.min.time()).replace(tzinfo=timezone.utc),
        status=DiscoveryStatus.searching,
    )
    db.add(job)
    db.commit()

    try:
        service = TwitterDiscoveryService(dummy_mode=body.dummy_mode)
        result = service.search_and_discover(
            keywords=all_keywords,
            location=body.location,
            since_date=body.date_from.isoformat(),
            until_date=body.date_to.isoformat(),
            max_results=body.max_results,
        )

        # Update the results
        result.seed_keywords = body.seed_keywords
        result.expanded_keywords = body.expanded_keywords
        result.dummy_mode = body.dummy_mode
        result.job_id = str(job.id)

        # Persist job results
        job.status = DiscoveryStatus.completed
        job.results_count = result.total_users_found
        job.tweets_scanned = result.total_tweets_scanned
        job.location_matched = result.location_matched_count
        job.results_data = {
            "users": [u.model_dump() for u in result.users],
            "profiled_users_count": result.profiled_users_count,
            "high_value_users_found": result.high_value_users_found,
            "selected_micro_influencers": [],
            "dummy_mode": body.dummy_mode,
        }
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        return result

    except Exception as exc:
        job.status = DiscoveryStatus.failed
        job.error_message = str(exc)[:2000]
        db.commit()
        log.error("Discovery search failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(exc)}")


@router.post("/save-users", response_model=SaveUsersResponse)
def save_discovered_users(body: SaveDiscoveredUsersRequest, db: Session = Depends(get_db)):
    """Save selected users from a discovery run into the social_profiles table."""
    job = db.query(DiscoveryJob).filter_by(id=uuid.UUID(body.discovery_job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Discovery job not found")
    if not job.results_data or "users" not in job.results_data:
        raise HTTPException(status_code=400, detail="No results data in this job")

    users_data = job.results_data["users"]
    saved_ids: list[str] = []

    for idx in body.user_indices:
        if idx < 0 or idx >= len(users_data):
            continue

        user = users_data[idx]

        # Check if profile already exists
        existing = (
            db.query(SocialProfile)
            .filter_by(platform="twitter", platform_user_id=user["platform_user_id"])
            .first()
        )
        if existing:
            saved_ids.append(str(existing.id))
            continue

        # Create new profile
        profile_id = uuid.uuid4()
        profile = SocialProfile(
            id=profile_id,
            platform="twitter",
            platform_user_id=user["platform_user_id"],
            username=user.get("username"),
            display_name=user.get("display_name"),
            bio=user.get("bio"),
            profile_image_url=user.get("profile_image_url"),
            location_raw=user.get("location_raw"),
            follower_count=user.get("follower_count"),
            following_count=user.get("following_count"),
            tweet_count=user.get("tweet_count"),
            source_method="api",
            last_collected=datetime.now(timezone.utc),
        )
        db.add(profile)
        db.flush()

        recent_tweets = user.get("last_10_tweets") or []
        matching_tweets = user.get("matching_tweets") or []
        tweets_to_store: list[dict] = []
        seen_tweet_ids: set[str] = set()
        for tweet_data in recent_tweets + matching_tweets:
            tweet_id = str(tweet_data.get("tweet_id") or "")
            if not tweet_id or tweet_id in seen_tweet_ids:
                continue
            seen_tweet_ids.add(tweet_id)
            tweets_to_store.append(tweet_data)

        # Save recent and matching tweets as posts
        for tweet_data in tweets_to_store:
            existing_post = (
                db.query(Post)
                .filter_by(platform_post_id=tweet_data["tweet_id"])
                .first()
            )
            if existing_post:
                continue

            post = Post(
                id=uuid.uuid4(),
                profile_id=profile_id,
                platform_post_id=tweet_data["tweet_id"],
                content=tweet_data.get("content", ""),
                post_type=tweet_data.get("post_type") or "tweet",
                likes=tweet_data.get("likes", 0),
                reposts=tweet_data.get("retweets", 0),
                replies=tweet_data.get("replies", 0),
            )
            if tweet_data.get("created_at"):
                try:
                    post.posted_at = datetime.fromisoformat(
                        tweet_data["created_at"].replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    pass
            db.add(post)

        saved_ids.append(str(profile_id))

    db.commit()
    return SaveUsersResponse(saved_count=len(saved_ids), profile_ids=saved_ids)


@router.patch("/{job_id}/users/{user_index}/manual-enrichment", response_model=DiscoveredUser)
def update_discovery_user_manual_enrichment(
    job_id: str,
    user_index: int,
    body: DiscoveryUserManualEnrichmentRequest,
    db: Session = Depends(get_db),
):
    job = _get_job_or_404(job_id, db)
    users_data = _get_job_users(job)
    if user_index < 0 or user_index >= len(users_data):
        raise HTTPException(status_code=404, detail="Discovery user not found")

    user = users_data[user_index]
    user["manual_followers_list"] = clean_manual_handle_list(body.followers_list)
    user["manual_following_list"] = clean_manual_handle_list(body.following_list)
    user["manual_notes"] = (body.notes or "").strip() or None

    results_data = dict(job.results_data or {})
    results_data["users"] = users_data
    results_data.setdefault("selected_micro_influencers", [])
    job.results_data = results_data
    db.add(job)
    db.commit()
    db.refresh(job)

    return DiscoveredUser(**user)


@router.post("/{job_id}/shared-followings/analyze", response_model=SharedFollowingsResponse)
def analyze_discovery_shared_followings(
    job_id: str,
    body: SharedFollowingsAnalyzeRequest,
    db: Session = Depends(get_db),
):
    job = _get_job_or_404(job_id, db)
    users_data = _get_job_users(job)
    selected_usernames = set((job.results_data or {}).get("selected_micro_influencers") or [])
    analyzed_handles, candidates = analyze_shared_followings(
        db=db,
        users_data=users_data,
        selected_indices=body.user_indices,
        min_overlap=body.min_overlap,
        max_candidates=body.max_candidates,
        preselected_usernames=selected_usernames,
    )
    return SharedFollowingsResponse(
        discovery_job_id=str(job.id),
        analyzed_user_handles=analyzed_handles,
        min_overlap=body.min_overlap,
        total_candidates=len(candidates),
        candidates=candidates,
    )


@router.patch("/{job_id}/shared-followings/selection", response_model=SharedFollowingsResponse)
def update_shared_followings_selection(
    job_id: str,
    body: SharedFollowingsSelectionRequest,
    db: Session = Depends(get_db),
):
    job = _get_job_or_404(job_id, db)
    users_data = _get_job_users(job)
    selected = clean_manual_handle_list(body.usernames)

    results_data = dict(job.results_data or {})
    results_data["selected_micro_influencers"] = selected
    job.results_data = results_data
    db.add(job)
    db.commit()
    db.refresh(job)

    user_indices = list(range(len(users_data)))
    analyzed_handles, candidates = analyze_shared_followings(
        db=db,
        users_data=users_data,
        selected_indices=user_indices,
        min_overlap=2,
        max_candidates=50,
        preselected_usernames=set(selected),
    )
    return SharedFollowingsResponse(
        discovery_job_id=str(job.id),
        analyzed_user_handles=analyzed_handles,
        min_overlap=2,
        total_candidates=len(candidates),
        candidates=candidates,
    )


@router.get("/{job_id}/export/csv")
def export_discovery_job_csv(job_id: str, db: Session = Depends(get_db)):
    job = _get_job_or_404(job_id, db)
    users_data = _get_job_users(job)
    data = DiscoveryExportService().build_csv(
        users=users_data,
        selected_micro_influencers=(job.results_data or {}).get("selected_micro_influencers", []),
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="discovery-{job.id}.csv"'},
    )


@router.get("/history", response_model=DiscoveryHistoryResponse)
def get_discovery_history(db: Session = Depends(get_db)):
    """Return past discovery runs, most recent first."""
    jobs = (
        db.query(DiscoveryJob)
        .order_by(DiscoveryJob.created_at.desc())
        .limit(50)
        .all()
    )
    return DiscoveryHistoryResponse(
        jobs=[
            DiscoveryJobSummary(
                id=str(j.id),
                platform=j.platform,
                dummy_mode=bool((j.results_data or {}).get("dummy_mode", False)),
                seed_keywords=j.seed_keywords or [],
                location=j.location,
                status=j.status.value if isinstance(j.status, DiscoveryStatus) else j.status,
                results_count=j.results_count or 0,
                tweets_scanned=j.tweets_scanned or 0,
                location_matched=j.location_matched or 0,
                created_at=j.created_at.isoformat() if j.created_at else "",
            )
            for j in jobs
        ]
    )


@router.get("/{job_id}", response_model=DiscoveryResponse)
def get_discovery_job(job_id: str, db: Session = Depends(get_db)):
    """Retrieve a specific discovery job's results."""
    job = db.query(DiscoveryJob).filter_by(id=uuid.UUID(job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Discovery job not found")

    users_data = (job.results_data or {}).get("users", [])

    from app.schemas.discovery import DiscoveredUser
    users = [DiscoveredUser(**u) for u in users_data]

    return DiscoveryResponse(
        job_id=str(job.id),
        status=job.status.value if isinstance(job.status, DiscoveryStatus) else job.status,
        dummy_mode=(job.results_data or {}).get("dummy_mode", False),
        seed_keywords=job.seed_keywords or [],
        expanded_keywords=job.expanded_keywords or [],
        location=job.location,
        users=users,
        total_tweets_scanned=job.tweets_scanned or 0,
        total_users_found=job.results_count or 0,
        location_matched_count=job.location_matched or 0,
        profiled_users_count=(job.results_data or {}).get("profiled_users_count", len(users)),
        high_value_users_found=(job.results_data or {}).get("high_value_users_found", 0),
        selected_micro_influencers=(job.results_data or {}).get("selected_micro_influencers", []),
    )
