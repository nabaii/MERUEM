from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models.social_profile import SocialProfile
from app.schemas.discovery import SharedFollowingCandidate

HANDLE_CHARS = re.compile(r"[^a-z0-9_./@-]+", re.IGNORECASE)


def clean_manual_handle_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()

    for raw in values or []:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue

        parts = re.split(r"[\n,;|]+", text)
        for part in parts:
            normalized = normalize_handle(part)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)

    return cleaned


def normalize_handle(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = HANDLE_CHARS.sub("", value.strip().lower())
    cleaned = cleaned.replace("https://x.com/", "").replace("http://x.com/", "")
    cleaned = cleaned.replace("https://twitter.com/", "").replace("http://twitter.com/", "")
    cleaned = cleaned.lstrip("@").strip("/")
    if not cleaned:
        return None
    return cleaned


def analyze_shared_followings(
    *,
    db: Session,
    users_data: list[dict],
    selected_indices: list[int],
    min_overlap: int = 2,
    max_candidates: int = 25,
    preselected_usernames: set[str] | None = None,
) -> tuple[list[str], list[SharedFollowingCandidate]]:
    selected_handles: list[str] = []
    overlap_map: dict[str, dict[str, object]] = defaultdict(
        lambda: {"count": 0, "followed_by_users": [], "source_indices": []}
    )

    discovered_lookup: dict[str, tuple[int, dict]] = {}
    for index, user in enumerate(users_data):
        username = normalize_handle(user.get("username"))
        if username:
            discovered_lookup[username] = (index, user)

    for idx in selected_indices:
        if idx < 0 or idx >= len(users_data):
            continue

        user = users_data[idx]
        selected_username = normalize_handle(user.get("username")) or f"user-{idx}"
        selected_handles.append(selected_username)
        following_list = clean_manual_handle_list(user.get("manual_following_list") or [])

        for handle in following_list:
            bucket = overlap_map[handle]
            source_indices = bucket["source_indices"]
            if idx in source_indices:
                continue
            source_indices.append(idx)
            bucket["count"] = int(bucket["count"]) + 1
            followed_by = bucket["followed_by_users"]
            followed_by.append(selected_username)

    candidates: list[SharedFollowingCandidate] = []
    selected_usernames = {normalize_handle(item) for item in preselected_usernames or set()} - {None}

    for username, overlap in overlap_map.items():
        overlap_count = int(overlap["count"])
        if overlap_count < min_overlap:
            continue

        discovered_user_index: int | None = None
        display_name: str | None = None
        follower_count: int | None = None
        high_value_score: float | None = None
        high_value_band: str | None = None
        user_type: str | None = None
        reasons: list[str] = [f"Followed by {overlap_count} selected users"]

        if username in discovered_lookup:
            discovered_user_index, discovered_user = discovered_lookup[username]
            display_name = discovered_user.get("display_name")
            follower_count = discovered_user.get("follower_count")
            high_value_score = discovered_user.get("high_value_score")
            high_value_band = discovered_user.get("high_value_band")
            user_type = discovered_user.get("user_type")
            reasons.append("Already exists in the profiled discovery list")
        else:
            existing_profile = (
                db.query(SocialProfile)
                .filter(SocialProfile.platform == "twitter", SocialProfile.username.ilike(username))
                .order_by(SocialProfile.follower_count.desc().nulls_last())
                .first()
            )
            if existing_profile:
                display_name = existing_profile.display_name
                follower_count = existing_profile.follower_count
                reasons.append("Matched an existing saved Twitter profile")

        fit_score = _micro_influencer_fit_score(
            overlap_count=overlap_count,
            follower_count=follower_count,
            high_value_score=high_value_score,
        )

        if follower_count is not None:
            if 1_000 <= follower_count <= 100_000:
                reasons.append("Follower count is within a typical micro-influencer range")
            elif follower_count < 1_000:
                reasons.append("Smaller audience but may still be a niche advocate")
            else:
                reasons.append("Audience may be too broad for a pure micro-influencer play")

        candidates.append(
            SharedFollowingCandidate(
                username=username,
                display_name=display_name,
                overlap_count=overlap_count,
                followed_by_users=sorted(set(overlap["followed_by_users"])),
                discovered_user_index=discovered_user_index,
                follower_count=follower_count,
                high_value_score=high_value_score,
                high_value_band=high_value_band,
                user_type=user_type,
                micro_influencer_fit_score=fit_score,
                reasons=reasons[:3],
                selected=username in selected_usernames,
            )
        )

    candidates.sort(
        key=lambda item: (
            item.micro_influencer_fit_score,
            item.overlap_count,
            item.high_value_score or 0.0,
            item.follower_count or 0,
        ),
        reverse=True,
    )
    return selected_handles, candidates[:max_candidates]


def _micro_influencer_fit_score(
    *,
    overlap_count: int,
    follower_count: int | None,
    high_value_score: float | None,
) -> float:
    overlap_score = min(100.0, overlap_count * 25.0)

    follower_score = 35.0
    if follower_count is not None:
        if 1_000 <= follower_count <= 100_000:
            follower_score = 100.0
        elif 500 <= follower_count < 1_000 or 100_000 < follower_count <= 150_000:
            follower_score = 75.0
        elif follower_count < 500:
            follower_score = 45.0
        else:
            follower_score = 55.0

    quality_score = high_value_score or 0.0
    return round(overlap_score * 0.45 + follower_score * 0.30 + quality_score * 0.25, 2)
