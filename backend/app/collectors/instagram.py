"""Instagram Graph API collector.

Collects public Instagram Business/Creator profiles and their recent media
using the Facebook Graph API v19.0.  Requires a long-lived Page Access Token
with `instagram_basic` and `pages_read_engagement` permissions.

Rate limits:
  - Graph API Business: ~4 800 calls / 24 h per token (soft cap)
  - We use exponential backoff on HTTP 429 / error code 32 / 17 responses.
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

PLATFORM = "instagram"
GRAPH_BASE = "https://graph.facebook.com"

PROFILE_FIELDS = ",".join([
    "id", "name", "username", "biography",
    "followers_count", "follows_count", "media_count",
    "profile_picture_url", "website",
])
MEDIA_FIELDS = ",".join([
    "id", "caption", "like_count", "comments_count",
    "timestamp", "media_type", "permalink",
])

# Instagram error codes that indicate rate limiting
_RATE_LIMIT_CODES = {4, 17, 32, 613}


class InstagramCollector:
    def __init__(self) -> None:
        if not settings.instagram_access_token:
            raise RuntimeError(
                "INSTAGRAM_ACCESS_TOKEN is not set. "
                "Add it to .env before running an Instagram collection."
            )
        self._token = settings.instagram_access_token
        self._api_version = settings.instagram_graph_api_version
        self._base = f"{GRAPH_BASE}/{self._api_version}"
        self._client = httpx.Client(timeout=30)

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def collect_from_usernames(
        self,
        seed_usernames: list[str],
        max_profiles: int = 1000,
        media_per_user: int = 50,
    ) -> list[dict]:
        """
        Collect Instagram profiles starting from seed usernames.
        Returns a list of parsed profile dicts.
        """
        collected: list[dict] = []
        seen: set[str] = set()

        for username in seed_usernames:
            if len(collected) >= max_profiles:
                break
            if username in seen:
                continue

            user_id = self._lookup_username(username)
            if not user_id:
                log.warning("Could not find Instagram user: %s", username)
                continue

            seen.add(username)
            profile = self._fetch_profile(user_id)
            if not profile:
                continue

            media = self._fetch_media(user_id, limit=media_per_user)
            parsed = self._parse_profile(profile, media)
            collected.append(parsed)
            log.info("Collected @%s (%d posts)", username, len(media))

        log.info("Instagram collection complete — %d profiles", len(collected))
        return collected

    def collect_from_user_ids(
        self,
        seed_user_ids: list[str],
        max_profiles: int = 1000,
        media_per_user: int = 50,
    ) -> list[dict]:
        """
        Collect Instagram profiles by known IG User IDs (faster — no username lookup step).
        """
        collected: list[dict] = []
        seen: set[str] = set()

        for user_id in seed_user_ids:
            if len(collected) >= max_profiles:
                break
            if user_id in seen:
                continue

            profile = self._fetch_profile(user_id)
            if not profile:
                continue
            seen.add(user_id)

            media = self._fetch_media(user_id, limit=media_per_user)
            parsed = self._parse_profile(profile, media)
            collected.append(parsed)
            log.info("Collected IG user %s (%d posts)", user_id, len(media))

        log.info("Instagram collection complete — %d profiles", len(collected))
        return collected

    # ------------------------------------------------------------------ #
    # Graph API calls with exponential backoff
    # ------------------------------------------------------------------ #

    def _get(self, path: str, params: dict | None = None) -> dict | None:
        """Make a GET request with exponential backoff on rate limits."""
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

                # Facebook API returns errors in the body even on HTTP 200
                if "error" in data:
                    code = data["error"].get("code", 0)
                    if code in _RATE_LIMIT_CODES:
                        wait = 2 ** attempt * 30
                        log.warning(
                            "Rate limit (code %d) on %s — waiting %ds", code, path, wait
                        )
                        time.sleep(wait)
                        continue
                    log.error("Graph API error on %s: %s", path, data["error"])
                    return None

                return data

            except httpx.HTTPError as exc:
                wait = 2 ** attempt * 5
                log.warning("HTTP error on %s: %s — retrying in %ds", path, exc, wait)
                time.sleep(wait)

        log.error("Giving up after %d attempts on %s", 6, path)
        return None

    def _lookup_username(self, username: str) -> str | None:
        """
        Search for an Instagram Business/Creator account by username.
        Returns the IG User ID or None.
        """
        data = self._get("ig/search", {"q": username, "type": "user", "fields": "id,name,username"})
        if not data:
            return None
        users = data.get("data", [])
        # Exact match on username (case-insensitive)
        for u in users:
            if (u.get("username") or "").lower() == username.lower():
                return u["id"]
        # Fallback: first result
        return users[0]["id"] if users else None

    def _fetch_profile(self, user_id: str) -> dict | None:
        data = self._get(user_id, {"fields": PROFILE_FIELDS})
        if data:
            raw_storage.save(PLATFORM, f"profile_{user_id}", data)
        return data

    def _fetch_media(self, user_id: str, limit: int = 50) -> list[dict]:
        media: list[dict] = []
        cursor: str | None = None

        while len(media) < limit:
            params: dict[str, Any] = {
                "fields": MEDIA_FIELDS,
                "limit": min(limit - len(media), 50),
            }
            if cursor:
                params["after"] = cursor

            data = self._get(f"{user_id}/media", params)
            if not data:
                break

            page = data.get("data", [])
            media.extend(page)
            raw_storage.save(PLATFORM, f"media_{user_id}_{uuid.uuid4().hex[:8]}", data)

            cursor = data.get("paging", {}).get("cursors", {}).get("after")
            if not cursor or not data.get("paging", {}).get("next"):
                break

        return media

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #

    def _parse_profile(self, user: dict, media: list[dict]) -> dict:
        followers = user.get("followers_count") or 0
        total_likes = sum(m.get("like_count") or 0 for m in media)
        total_comments = sum(m.get("comments_count") or 0 for m in media)
        media_count = user.get("media_count") or len(media)

        engagement_rate: float | None = None
        if followers > 0 and media_count > 0:
            engagement_rate = round(
                (total_likes + total_comments) / media_count / followers, 6
            )

        return {
            "platform": PLATFORM,
            "platform_user_id": str(user["id"]),
            "username": user.get("username"),
            "display_name": user.get("name"),
            "bio": user.get("biography"),
            "profile_image_url": user.get("profile_picture_url"),
            "location_raw": None,  # Graph API no longer exposes location
            "follower_count": user.get("followers_count"),
            "following_count": user.get("follows_count"),
            "tweet_count": media_count,  # reused as generic post/media count
            "engagement_rate": engagement_rate,
            "last_collected": datetime.now(timezone.utc).isoformat(),
            "posts": [self._parse_media(m) for m in media],
        }

    @staticmethod
    def _parse_media(item: dict) -> dict:
        return {
            "platform_post_id": str(item["id"]),
            "content": item.get("caption") or "",
            "post_type": (item.get("media_type") or "IMAGE").lower(),
            "likes": item.get("like_count"),
            "reposts": 0,
            "replies": item.get("comments_count"),
            "entities": None,
            "language": None,
            "posted_at": item.get("timestamp"),
        }

    # ------------------------------------------------------------------ #
    # DB persistence (called by Celery task)
    # ------------------------------------------------------------------ #

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
