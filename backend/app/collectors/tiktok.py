"""
TikTok collector using Playwright stealth scraping.
Intercepts TikTok's SIGI_STATE / __UNIVERSAL_DATA_FOR_REHYDRATION__ hydration JSON
for reliable data extraction, with DOM fallback.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.collectors.bot_base import BotScraper, _random_delay
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

log = logging.getLogger(__name__)

TIKTOK_PROFILE_URL = "https://www.tiktok.com/@{username}"


def _parse_count(text: str) -> int:
    """Convert TikTok abbreviated counts (1.2M, 34.5K) to integer."""
    text = str(text).strip().upper().replace(",", "")
    try:
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        return int(float(text))
    except (ValueError, IndexError):
        return 0


class TikTokCollector:
    """
    Collects TikTok user profiles and recent videos via headless browser scraping.
    Primary path: intercept SIGI_STATE JSON from page HTML (no API key required).
    Fallback path: direct DOM element extraction.
    """

    def __init__(self, use_proxy: bool = True, headless: bool = True) -> None:
        self.use_proxy = use_proxy
        self.headless = headless

    def collect_from_usernames(
        self,
        seed_usernames: list[str],
        max_profiles: int = 500,
        videos_per_user: int = 20,
    ) -> list[dict]:
        """Synchronous entry point (Celery-compatible). Runs async collection in a new loop."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._async_collect(seed_usernames, max_profiles, videos_per_user)
            )
        finally:
            loop.close()

    async def _async_collect(
        self,
        seed_usernames: list[str],
        max_profiles: int,
        videos_per_user: int,
    ) -> list[dict]:
        results: list[dict] = []
        async with BotScraper(
            platform="tiktok",
            use_proxy=self.use_proxy,
            headless=self.headless,
        ) as bot:
            for username in seed_usernames[:max_profiles]:
                try:
                    profile_data = await self._fetch_profile(bot, username, videos_per_user)
                    if profile_data:
                        results.append(profile_data)
                        log.info(
                            "TikTok: collected @%s — %d followers",
                            username,
                            profile_data.get("follower_count", 0),
                        )
                    await _random_delay(2500, 7000)
                except Exception as exc:
                    log.warning("TikTok: failed to collect @%s: %s", username, exc)
        return results

    async def _fetch_profile(
        self, bot: BotScraper, username: str, videos_per_user: int
    ) -> Optional[dict]:
        """Scrape a TikTok profile page and return structured profile + video data."""
        url = TIKTOK_PROFILE_URL.format(username=username)
        page = await bot.new_page()
        try:
            success = await bot.navigate(page, url)
            if not success:
                return None

            # Give the page JS time to hydrate SIGI_STATE
            await _random_delay(1500, 3000)
            await bot.scroll_to_load(page, times=2)

            content = await page.content()

            # Primary: extract from TikTok hydration JSON
            profile = self._parse_sigi_state(content, username)
            if not profile:
                # Fallback: DOM-based extraction
                profile = await self._parse_dom_profile(page, username)

            if profile:
                videos = await self._collect_videos(bot, page, username, videos_per_user)
                profile["posts"] = videos

            return profile
        finally:
            await page.close()

    # ── Data extraction ───────────────────────────────────────────────────────

    def _parse_sigi_state(self, html: str, username: str) -> Optional[dict]:
        """Extract profile data from TikTok's SIGI_STATE / UNIVERSAL_DATA hydration JSON."""
        # Try SIGI_STATE first
        match = re.search(
            r'<script id="SIGI_STATE"[^>]*>(.*?)</script>', html, re.DOTALL
        )
        if not match:
            match = re.search(
                r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )
        if not match:
            return None

        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, IndexError):
            return None

        user_info: dict = {}
        stats: dict = {}

        # Path 1: SIGI_STATE → UserPage.userInfo
        try:
            ui = data.get("UserPage", {}).get("userInfo", {})
            if ui:
                user_info = ui.get("user", {})
                stats = ui.get("stats", {})
        except Exception:
            pass

        # Path 2: __DEFAULT_SCOPE__ → webapp.user-detail
        if not user_info:
            try:
                scope = data.get("__DEFAULT_SCOPE__", {})
                ui = scope.get("webapp.user-detail", {}).get("userInfo", {})
                user_info = ui.get("user", {})
                stats = ui.get("stats", {})
            except Exception:
                pass

        if not user_info:
            return None

        follower_count: int = stats.get("followerCount", 0)
        following_count: int = stats.get("followingCount", 0)
        video_count: int = stats.get("videoCount", 0)
        heart_count: int = stats.get("heartCount", 0)

        engagement_rate = 0.0
        if follower_count > 0 and video_count > 0:
            engagement_rate = round(
                (heart_count / video_count) / follower_count * 100, 4
            )

        return {
            "platform": "tiktok",
            "platform_user_id": str(user_info.get("id", f"tiktok_{username}")),
            "username": user_info.get("uniqueId", username).lower(),
            "display_name": user_info.get("nickname", username),
            "bio": user_info.get("signature", ""),
            "profile_image_url": (
                user_info.get("avatarLarger") or user_info.get("avatarMedium")
            ),
            "follower_count": follower_count,
            "following_count": following_count,
            "tweet_count": video_count,
            "verified": bool(user_info.get("verified", False)),
            "engagement_rate": engagement_rate,
            "location_raw": user_info.get("region", ""),
            "source_method": "bot",
            "last_collected": datetime.now(timezone.utc),
        }

    async def _parse_dom_profile(self, page, username: str) -> Optional[dict]:
        """DOM fallback — used when SIGI_STATE JSON is not available."""
        display_name = username
        bio = ""
        follower_count = 0
        following_count = 0

        try:
            el = page.locator('h1[data-e2e="user-title"]').first
            if await el.count() > 0:
                display_name = await el.inner_text(timeout=5000)
        except Exception:
            pass

        try:
            el = page.locator('h2[data-e2e="user-bio"]').first
            if await el.count() > 0:
                bio = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator('[data-e2e="followers-count"]').first
            if await el.count() > 0:
                follower_count = _parse_count(await el.inner_text(timeout=3000))
        except Exception:
            pass

        try:
            el = page.locator('[data-e2e="following-count"]').first
            if await el.count() > 0:
                following_count = _parse_count(await el.inner_text(timeout=3000))
        except Exception:
            pass

        return {
            "platform": "tiktok",
            "platform_user_id": f"tiktok_{username}",
            "username": username.lower(),
            "display_name": display_name,
            "bio": bio,
            "profile_image_url": None,
            "follower_count": follower_count,
            "following_count": following_count,
            "tweet_count": 0,
            "verified": False,
            "engagement_rate": 0.0,
            "location_raw": "",
            "source_method": "bot",
            "last_collected": datetime.now(timezone.utc),
        }

    async def _collect_videos(
        self, bot: BotScraper, page, username: str, limit: int
    ) -> list[dict]:
        """Collect recent video posts from the profile page after scrolling."""
        videos: list[dict] = []
        try:
            await bot.scroll_to_load(page, times=3)
            cards = page.locator('[data-e2e="user-post-item"]')
            count = min(await cards.count(), limit)
            for i in range(count):
                card = cards.nth(i)
                try:
                    video = await self._parse_video_card(card)
                    if video:
                        videos.append(video)
                except Exception:
                    pass
        except Exception as exc:
            log.debug("TikTok video collection error for @%s: %s", username, exc)
        return videos

    async def _parse_video_card(self, card) -> Optional[dict]:
        """Parse a single TikTok video card DOM element into a post dict."""
        try:
            caption = ""
            try:
                cap_el = card.locator('[data-e2e="video-desc"]').first
                if await cap_el.count() > 0:
                    caption = await cap_el.inner_text(timeout=2000)
            except Exception:
                pass

            hashtags = re.findall(r"#(\w+)", caption)

            like_count = 0
            try:
                like_el = card.locator('[data-e2e="video-like-count"]').first
                if await like_el.count() > 0:
                    like_count = _parse_count(await like_el.inner_text(timeout=2000))
            except Exception:
                pass

            return {
                "platform_post_id": f"tt_{uuid.uuid4().hex[:14]}",
                "content": caption[:4000],
                "post_type": "video",
                "likes": like_count,
                "reposts": 0,
                "replies": 0,
                "entities": {"hashtags": hashtags, "mentions": [], "urls": []},
                "posted_at": datetime.now(timezone.utc),
                "is_processed": False,
            }
        except Exception:
            return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def upsert_profile(self, db: Session, profile_data: dict) -> SocialProfile:
        """Upsert a TikTok profile + its videos into the database."""
        posts_data: list[dict] = profile_data.pop("posts", [])

        profile = (
            db.query(SocialProfile)
            .filter(
                SocialProfile.platform == "tiktok",
                SocialProfile.platform_user_id == profile_data["platform_user_id"],
            )
            .first()
        )

        if profile:
            for key, val in profile_data.items():
                if hasattr(profile, key) and val is not None:
                    setattr(profile, key, val)
        else:
            profile = SocialProfile(**profile_data)
            db.add(profile)

        db.flush()

        for post_data in posts_data:
            pid = post_data.get("platform_post_id")
            if pid:
                exists = (
                    db.query(Post)
                    .filter(Post.profile_id == profile.id, Post.platform_post_id == pid)
                    .first()
                )
                if exists:
                    continue
            post = Post(id=uuid.uuid4(), profile_id=profile.id, **post_data)
            db.add(post)

        return profile
