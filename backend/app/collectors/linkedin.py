"""
LinkedIn collector — API-first with Playwright bot fallback.
Uses LinkedIn's unofficial public search for organic profiles and company pages.
LinkedIn Marketing API (if credentials supplied) handles authenticated B2B data.
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.collectors.bot_base import BotScraper, _random_delay
from app.core.config import settings
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

log = logging.getLogger(__name__)

LINKEDIN_PROFILE_URL = "https://www.linkedin.com/in/{slug}/"
LINKEDIN_COMPANY_URL = "https://www.linkedin.com/company/{slug}/"
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"


class LinkedInCollector:
    """
    Collects LinkedIn profiles using a two-path strategy:
    1. LinkedIn Marketing API (requires OAuth app credentials) — for company pages
    2. Playwright bot scraping — for public personal profiles and companies without API access

    The API path is used automatically when `linkedin_client_id` and
    `linkedin_access_token` are configured in settings.
    """

    def __init__(self, use_proxy: bool = True, headless: bool = True) -> None:
        self.use_proxy = use_proxy
        self.headless = headless
        self._has_api = bool(settings.linkedin_client_id and settings.linkedin_access_token)

    # ── Public entry points ───────────────────────────────────────────────────

    def collect_from_usernames(
        self,
        seed_usernames: list[str],
        max_profiles: int = 300,
        posts_per_profile: int = 10,
        profile_type: str = "person",  # "person" | "company"
    ) -> list[dict]:
        """Synchronous entry point (Celery-compatible)."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._async_collect(seed_usernames, max_profiles, posts_per_profile, profile_type)
            )
        finally:
            loop.close()

    # ── Orchestration ─────────────────────────────────────────────────────────

    async def _async_collect(
        self,
        seed_usernames: list[str],
        max_profiles: int,
        posts_per_profile: int,
        profile_type: str,
    ) -> list[dict]:
        results: list[dict] = []

        async with BotScraper(
            platform="linkedin",
            use_proxy=self.use_proxy,
            headless=self.headless,
        ) as bot:
            for slug in seed_usernames[:max_profiles]:
                try:
                    # Try API first if credentials are available
                    profile: Optional[dict] = None
                    if self._has_api and profile_type == "company":
                        profile = await self._fetch_via_api(slug)

                    # Fall back to bot scraping
                    if not profile:
                        profile = await self._fetch_via_bot(bot, slug, profile_type, posts_per_profile)

                    if profile:
                        results.append(profile)
                        log.info(
                            "LinkedIn: collected %s (%s connections)",
                            slug,
                            profile.get("follower_count", "?"),
                        )
                    await _random_delay(4000, 10000)
                except Exception as exc:
                    log.warning("LinkedIn: failed to collect %s: %s", slug, exc)

        return results

    # ── API path ──────────────────────────────────────────────────────────────

    async def _fetch_via_api(self, slug: str) -> Optional[dict]:
        """
        Fetch a LinkedIn Company Page via the Marketing API.
        Requires linkedin_access_token with r_organization_social scope.
        """
        headers = {
            "Authorization": f"Bearer {settings.linkedin_access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        url = f"{LINKEDIN_API_BASE}/organizations?q=vanityName&vanityName={quote(slug)}"
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                elements = data.get("elements", [])
                if not elements:
                    return None
                org = elements[0]
                return self._parse_api_org(org, slug)
        except httpx.HTTPStatusError as exc:
            log.warning("LinkedIn API error for %s: %s", slug, exc.response.status_code)
            return None
        except Exception as exc:
            log.warning("LinkedIn API unexpected error for %s: %s", slug, exc)
            return None

    def _parse_api_org(self, org: dict, slug: str) -> dict:
        """Map LinkedIn API organisation response to the internal profile schema."""
        name = ""
        try:
            name = org.get("localizedName", "") or org.get("name", {}).get(
                "localized", {}
            ).get("en_US", slug)
        except Exception:
            name = slug

        description = ""
        try:
            description = org.get("localizedDescription", "") or ""
        except Exception:
            pass

        follower_count = org.get("followersCount", 0) or 0

        return {
            "platform": "linkedin",
            "platform_user_id": str(org.get("id", f"li_{slug}")),
            "username": slug.lower(),
            "display_name": name,
            "bio": description[:1000],
            "profile_image_url": None,
            "follower_count": follower_count,
            "following_count": 0,
            "tweet_count": 0,
            "verified": False,
            "engagement_rate": 0.0,
            "location_raw": org.get("headquartersAddress", {}).get("city", ""),
            "source_method": "api",
            "last_collected": datetime.now(timezone.utc),
            "posts": [],
        }

    # ── Bot scraping path ─────────────────────────────────────────────────────

    async def _fetch_via_bot(
        self,
        bot: BotScraper,
        slug: str,
        profile_type: str,
        posts_per_profile: int,
    ) -> Optional[dict]:
        """Scrape a LinkedIn public profile via headless browser."""
        url = (
            LINKEDIN_COMPANY_URL.format(slug=slug)
            if profile_type == "company"
            else LINKEDIN_PROFILE_URL.format(slug=slug)
        )
        page = await bot.new_page()
        try:
            success = await bot.navigate(page, url, wait_until="networkidle", timeout=40_000)
            if not success:
                return None

            # Detect login wall
            current_url = page.url
            if "authwall" in current_url or "/login" in current_url:
                log.warning("LinkedIn login wall encountered for %s", slug)
                bot.invalidate_session()
                return None

            await _random_delay(1500, 3500)
            await bot.scroll_to_load(page, times=3)

            content = await page.content()
            profile = (
                await self._parse_company_page(page, content, slug)
                if profile_type == "company"
                else await self._parse_person_page(page, content, slug)
            )

            if profile:
                posts = await self._collect_posts(page, posts_per_profile)
                profile["posts"] = posts

            return profile
        finally:
            await page.close()

    async def _parse_person_page(self, page, html: str, slug: str) -> Optional[dict]:
        """Extract person profile data from LinkedIn public profile page."""
        display_name = slug
        headline = ""
        location = ""
        about = ""
        connections_text = ""

        try:
            el = page.locator("h1.text-heading-xlarge").first
            if await el.count() > 0:
                display_name = await el.inner_text(timeout=5000)
        except Exception:
            pass

        try:
            el = page.locator("div.text-body-medium.break-words").first
            if await el.count() > 0:
                headline = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator("span.text-body-small.inline.t-black--light.break-words").first
            if await el.count() > 0:
                location = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator("div.display-flex.ph5.pv3").first
            if await el.count() > 0:
                about = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator("span.t-bold").first
            if await el.count() > 0:
                connections_text = await el.inner_text(timeout=3000)
        except Exception:
            pass

        follower_count = self._parse_connections(connections_text)

        # Extract numeric ID from JSON-LD if available
        platform_id = f"li_{slug}"
        try:
            jsonld_match = re.search(r'"identifier"\s*:\s*\{[^}]*"value"\s*:\s*"([^"]+)"', html)
            if jsonld_match:
                platform_id = jsonld_match.group(1)
        except Exception:
            pass

        bio = (headline + ". " + about).strip()[:1000]

        return {
            "platform": "linkedin",
            "platform_user_id": platform_id,
            "username": slug.lower(),
            "display_name": display_name.strip(),
            "bio": bio,
            "profile_image_url": None,
            "follower_count": follower_count,
            "following_count": 0,
            "tweet_count": 0,
            "verified": False,
            "engagement_rate": 0.0,
            "location_raw": location.strip(),
            "source_method": "bot",
            "last_collected": datetime.now(timezone.utc),
        }

    async def _parse_company_page(self, page, html: str, slug: str) -> Optional[dict]:
        """Extract company profile data from LinkedIn company page."""
        company_name = slug
        tagline = ""
        about = ""
        follower_text = ""
        location = ""

        try:
            el = page.locator("h1.org-top-card-summary__title").first
            if await el.count() > 0:
                company_name = await el.inner_text(timeout=5000)
        except Exception:
            pass

        try:
            el = page.locator("p.org-top-card-summary__tagline").first
            if await el.count() > 0:
                tagline = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator("p.org-top-card-summary__follower-count").first
            if await el.count() > 0:
                follower_text = await el.inner_text(timeout=3000)
        except Exception:
            pass

        try:
            el = page.locator("p.org-top-card-summary__headquarter").first
            if await el.count() > 0:
                location = await el.inner_text(timeout=3000)
        except Exception:
            pass

        follower_count = self._parse_connections(follower_text)

        return {
            "platform": "linkedin",
            "platform_user_id": f"li_co_{slug}",
            "username": slug.lower(),
            "display_name": company_name.strip(),
            "bio": (tagline + " " + about).strip()[:1000],
            "profile_image_url": None,
            "follower_count": follower_count,
            "following_count": 0,
            "tweet_count": 0,
            "verified": False,
            "engagement_rate": 0.0,
            "location_raw": location.strip(),
            "source_method": "bot",
            "last_collected": datetime.now(timezone.utc),
        }

    async def _collect_posts(self, page, limit: int) -> list[dict]:
        """Collect recent LinkedIn posts/activity from the profile page."""
        posts: list[dict] = []
        try:
            post_els = page.locator("div.feed-shared-update-v2")
            count = min(await post_els.count(), limit)
            for i in range(count):
                el = post_els.nth(i)
                try:
                    text_el = el.locator("span.break-words").first
                    content = ""
                    if await text_el.count() > 0:
                        content = await text_el.inner_text(timeout=2000)
                    hashtags = re.findall(r"#(\w+)", content)
                    posts.append(
                        {
                            "platform_post_id": f"li_{uuid.uuid4().hex[:12]}",
                            "content": content[:4000],
                            "post_type": "post",
                            "likes": 0,
                            "reposts": 0,
                            "replies": 0,
                            "entities": {"hashtags": hashtags, "mentions": [], "urls": []},
                            "posted_at": datetime.now(timezone.utc),
                            "is_processed": False,
                        }
                    )
                except Exception:
                    pass
        except Exception as exc:
            log.debug("LinkedIn post collection error: %s", exc)
        return posts

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_connections(self, text: str) -> int:
        """Parse LinkedIn follower/connection text ('12,345 followers', '500+') to int."""
        if not text:
            return 0
        text = text.strip().replace(",", "").lower()
        # Remove non-numeric suffix words
        num_match = re.search(r"[\d.]+[kmb]?", text)
        if not num_match:
            return 0
        raw = num_match.group(0)
        try:
            if raw.endswith("k"):
                return int(float(raw[:-1]) * 1_000)
            if raw.endswith("m"):
                return int(float(raw[:-1]) * 1_000_000)
            if raw.endswith("b"):
                return int(float(raw[:-1]) * 1_000_000_000)
            return int(float(raw))
        except ValueError:
            return 0

    # ── Persistence ───────────────────────────────────────────────────────────

    def upsert_profile(self, db: Session, profile_data: dict) -> SocialProfile:
        """Upsert a LinkedIn profile and its posts into the database."""
        posts_data: list[dict] = profile_data.pop("posts", [])

        profile = (
            db.query(SocialProfile)
            .filter(
                SocialProfile.platform == "linkedin",
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
