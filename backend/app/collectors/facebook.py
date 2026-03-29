"""Facebook Graph API collector.

Collects public Facebook Pages and their recent posts using the Graph API v19.0.
Requires a valid Access Token (Page or App token with appropriate permissions).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.storage import raw_storage
from app.core.config import settings
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

log = logging.getLogger(__name__)

PLATFORM = "facebook"
GRAPH_BASE = "https://graph.facebook.com"

PROFILE_FIELDS = ",".join([
    "id", "name", "username", "about",
    "followers_count", "fan_count",  # fan_count is likes
    "picture.type(large)", "website"
])

MEDIA_FIELDS = ",".join([
    "id", "message", "created_time",
    "shares", "likes.summary(true)", "comments.summary(true)",
    "permalink_url"
])

_RATE_LIMIT_CODES = {4, 17, 32, 613}


class FacebookCollector:
    def __init__(self) -> None:
        if not settings.facebook_access_token:
            raise RuntimeError(
                "FACEBOOK_ACCESS_TOKEN is not set. "
                "Add it to .env before running a Facebook collection."
            )
        self._token = settings.facebook_access_token
        self._api_version = settings.facebook_graph_api_version
        self._base = f"{GRAPH_BASE}/{self._api_version}"
        self._client = httpx.Client(timeout=30)

    def collect_from_usernames(
        self,
        seed_usernames: list[str],
        max_profiles: int = 1000,
        posts_per_page: int = 50,
    ) -> list[dict]:
        """Collect Facebook Pages starting from seed usernames/screen names."""
        collected: list[dict] = []
        seen: set[str] = set()

        for username in seed_usernames:
            if len(collected) >= max_profiles:
                break
            if username in seen:
                continue

            # Facebook allows querying by username directly resolving to ID for pages
            seen.add(username)
            profile = self._fetch_profile(username)
            if not profile:
                continue

            page_id = profile.get("id")
            if not page_id:
                continue

            media = self._fetch_media(page_id, limit=posts_per_page)
            parsed = self._parse_profile(profile, media)
            collected.append(parsed)
            log.info("Collected %s (%d posts)", username, len(media))

        log.info("Facebook collection complete — %d profiles", len(collected))
        return collected

    def collect_from_page_ids(
        self,
        seed_page_ids: list[str],
        max_profiles: int = 1000,
        posts_per_page: int = 50,
    ) -> list[dict]:
        collected: list[dict] = []
        seen: set[str] = set()

        for page_id in seed_page_ids:
            if len(collected) >= max_profiles:
                break
            if page_id in seen:
                continue

            seen.add(page_id)
            profile = self._fetch_profile(page_id)
            if not profile:
                continue

            media = self._fetch_media(page_id, limit=posts_per_page)
            parsed = self._parse_profile(profile, media)
            collected.append(parsed)
            log.info("Collected FB Page %s (%d posts)", page_id, len(media))

        log.info("Facebook collection complete — %d profiles", len(collected))
        return collected

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        url = f"{self._base}/{path.lstrip('/')}"
        p = {"access_token": self._token, **(params or {})}

        for attempt in range(6):
            try:
                resp = self._client.get(url, params=p)

                if resp.status_code == 429:
                    wait = 2 ** attempt * 30
                    log.warning("HTTP 429 on %s — waiting %ds", path, wait)
                    time.sleep(wait)
                    continue

                data = resp.json()

                if "error" in data:
                    code = data["error"].get("code", 0)
                    if code in _RATE_LIMIT_CODES:
                        wait = 2 ** attempt * 30
                        log.warning(
                            "Rate limit (code %d) on %s — waiting %ds", code, path, wait
                        )
                        time.sleep(wait)
                        continue
                    log.error("FB Graph API error on %s: %s", path, data["error"])
                    return None

                return data

            except httpx.HTTPError as exc:
                wait = 2 ** attempt * 5
                log.warning("HTTP error on %s: %s — retrying in %ds", path, exc, wait)
                time.sleep(wait)

        log.error("Giving up after 6 attempts on %s", path)
        return None

    def _fetch_profile(self, page_id_or_username: str) -> dict | None:
        data = self._get(page_id_or_username, {"fields": PROFILE_FIELDS})
        if data:
            raw_storage.save(PLATFORM, f"profile_{data.get('id', page_id_or_username)}", data)
        return data

    def _fetch_media(self, page_id: str, limit: int = 50) -> list[dict]:
        media: list[dict] = []
        cursor: str | None = None

        while len(media) < limit:
            params: dict[str, Any] = {
                "fields": MEDIA_FIELDS,
                "limit": min(limit - len(media), 50),
            }
            if cursor:
                params["after"] = cursor

            data = self._get(f"{page_id}/posts", params)
            if not data:
                break

            page = data.get("data", [])
            media.extend(page)
            raw_storage.save(PLATFORM, f"posts_{page_id}_{uuid.uuid4().hex[:8]}", data)

            cursor = data.get("paging", {}).get("cursors", {}).get("after")
            if not cursor or not data.get("paging", {}).get("next"):
                break

        return media

    def _parse_profile(self, user: dict, media: list[dict]) -> dict:
        followers = user.get("followers_count") or user.get("fan_count") or 0
        
        parsed_posts = [self._parse_media(m) for m in media]
        
        total_likes = sum(p.get("likes") or 0 for p in parsed_posts)
        total_comments = sum(p.get("replies") or 0 for p in parsed_posts)
        media_count = len(parsed_posts)

        engagement_rate: float | None = None
        if followers > 0 and media_count > 0:
            engagement_rate = round(
                (total_likes + total_comments) / media_count / followers, 6
            )

        picture_data = user.get("picture", {}).get("data", {})
        profile_image_url = picture_data.get("url")

        return {
            "platform": PLATFORM,
            "platform_user_id": str(user["id"]),
            "username": user.get("username"),
            "display_name": user.get("name"),
            "bio": user.get("about"),
            "profile_image_url": profile_image_url,
            "location_raw": None, 
            "follower_count": followers,
            "following_count": 0, 
            "tweet_count": media_count,
            "engagement_rate": engagement_rate,
            "last_collected": datetime.now(timezone.utc).isoformat(),
            "posts": parsed_posts,
        }

    @staticmethod
    def _parse_media(item: dict) -> dict:
        likes_data = item.get("likes", {}).get("summary", {})
        likes_count = likes_data.get("total_count", 0)
        
        comments_data = item.get("comments", {}).get("summary", {})
        comments_count = comments_data.get("total_count", 0)
        
        shares_data = item.get("shares", {})
        shares_count = shares_data.get("count", 0)

        return {
            "platform_post_id": str(item.get("id", "")),
            "content": item.get("message") or "",
            "post_type": "text", 
            "likes": likes_count,
            "reposts": shares_count,
            "replies": comments_count,
            "entities": None,
            "language": None,
            "posted_at": item.get("created_time"),
        }

    def upsert_profile(self, db_session: Any, parsed: dict) -> SocialProfile:
        profile = (
            db_session.query(SocialProfile)
            .filter_by(
                platform=parsed["platform"],
                platform_user_id=parsed["platform_user_id"],
            )
            .first()
        )
        if profile is None:
            profile = SocialProfile(id=uuid.uuid4())

        for field in (
            "platform", "platform_user_id", "username", "display_name",
            "bio", "profile_image_url", "location_raw",
            "follower_count", "following_count", "tweet_count", "engagement_rate",
        ):
            setattr(profile, field, parsed.get(field))

        profile.last_collected = datetime.now(timezone.utc)
        db_session.add(profile)
        db_session.flush()

        for post_data in parsed.get("posts", []):
            existing = (
                db_session.query(Post)
                .filter_by(platform_post_id=post_data["platform_post_id"])
                .first()
            )
            if existing:
                continue
            post = Post(
                id=uuid.uuid4(),
                profile_id=profile.id,
                **{k: v for k, v in post_data.items() if k != "posted_at"},
            )
            raw = post_data.get("posted_at")
            if raw:
                post.posted_at = (
                    datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    if isinstance(raw, str)
                    else raw
                )
            db_session.add(post)

        return profile
