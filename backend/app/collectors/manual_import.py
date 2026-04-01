"""
Manual data ingestion processor.
Handles CSV/Excel bulk upload, column mapping, and URL-based profile enrichment
via bot scraping (visits the URL and fills in profile data automatically).
"""

import asyncio
import io
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

# Supported CSV column aliases mapped to internal field names
COLUMN_ALIASES: dict[str, str] = {
    # username variants
    "username": "username",
    "handle": "username",
    "user": "username",
    "screen_name": "username",
    # platform
    "platform": "platform",
    "network": "platform",
    "social_network": "platform",
    # display_name variants
    "display_name": "display_name",
    "name": "display_name",
    "full_name": "display_name",
    "account_name": "display_name",
    # bio/description
    "bio": "bio",
    "description": "bio",
    "about": "bio",
    "summary": "bio",
    # follower count
    "follower_count": "follower_count",
    "followers": "follower_count",
    "followers_count": "follower_count",
    # following count
    "following_count": "following_count",
    "following": "following_count",
    # location
    "location": "location_raw",
    "location_raw": "location_raw",
    "city": "location_raw",
    "country": "location_raw",
    # profile URL
    "profile_url": "profile_url",
    "url": "profile_url",
    "link": "profile_url",
    "website": "profile_url",
    # profile image
    "profile_image_url": "profile_image_url",
    "avatar": "profile_image_url",
    "photo": "profile_image_url",
    # email (stored for enrichment, not in SocialProfile schema)
    "email": "email",
    "email_address": "email",
    # phone
    "phone": "phone",
    "phone_number": "phone",
    "whatsapp": "phone",
}

# Platform name normalisation
PLATFORM_ALIASES: dict[str, str] = {
    "twitter": "twitter",
    "x": "twitter",
    "x.com": "twitter",
    "instagram": "instagram",
    "ig": "instagram",
    "insta": "instagram",
    "facebook": "facebook",
    "fb": "facebook",
    "tiktok": "tiktok",
    "tik tok": "tiktok",
    "linkedin": "linkedin",
    "li": "linkedin",
    "whatsapp": "whatsapp",
    "wa": "whatsapp",
    "youtube": "youtube",
    "yt": "youtube",
    "snapchat": "snapchat",
    "snap": "snapchat",
}

# URL → platform detection
URL_PLATFORM_PATTERNS: list[tuple[str, str]] = [
    (r"tiktok\.com/@", "tiktok"),
    (r"tiktok\.com/", "tiktok"),
    (r"linkedin\.com/in/", "linkedin"),
    (r"linkedin\.com/company/", "linkedin"),
    (r"instagram\.com/", "instagram"),
    (r"twitter\.com/", "twitter"),
    (r"x\.com/", "twitter"),
    (r"facebook\.com/", "facebook"),
    (r"fb\.com/", "facebook"),
    (r"youtube\.com/", "youtube"),
    (r"youtu\.be/", "youtube"),
]


def _detect_platform_from_url(url: str) -> Optional[str]:
    """Infer the platform from a profile URL."""
    url_lower = url.lower()
    for pattern, platform in URL_PLATFORM_PATTERNS:
        if re.search(pattern, url_lower):
            return platform
    return None


def _extract_slug_from_url(url: str, platform: str) -> str:
    """Extract the username/slug from a social media profile URL."""
    url = url.rstrip("/")
    patterns: dict[str, str] = {
        "tiktok": r"tiktok\.com/@([^/?]+)",
        "linkedin": r"linkedin\.com/(?:in|company)/([^/?]+)",
        "instagram": r"instagram\.com/([^/?]+)",
        "twitter": r"(?:twitter|x)\.com/([^/?]+)",
        "facebook": r"facebook\.com/([^/?]+)",
        "youtube": r"youtube\.com/(?:@|channel/|c/|user/)?([^/?]+)",
    }
    pat = patterns.get(platform)
    if pat:
        m = re.search(pat, url, re.IGNORECASE)
        if m:
            return m.group(1)
    # Fallback: last URL segment
    return url.split("/")[-1].lstrip("@")


def _safe_int(val) -> Optional[int]:
    """Convert a value to int safely, stripping commas and K/M suffixes."""
    if val is None:
        return None
    text = str(val).strip().replace(",", "").upper()
    try:
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        return int(float(text))
    except (ValueError, TypeError):
        return None


class ManualImportProcessor:
    """
    Handles three ingestion modes:
    1. CSV / Excel bulk upload with flexible column mapping
    2. Single URL enrichment — bot visits the URL and scrapes profile data
    3. Bulk URL list enrichment — batch of URLs processed sequentially
    """

    def __init__(self, use_proxy: bool = True, headless: bool = True) -> None:
        self.use_proxy = use_proxy
        self.headless = headless

    # ── CSV / Excel ingestion ─────────────────────────────────────────────────

    def parse_csv(
        self,
        file_content: bytes,
        filename: str = "upload.csv",
        default_platform: str = "unknown",
    ) -> list[dict]:
        """
        Parse a CSV or Excel file and return a list of normalised profile dicts.
        Columns are mapped flexibly via COLUMN_ALIASES.
        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError("pandas is required for CSV import: pip install pandas openpyxl") from exc

        file_like = io.BytesIO(file_content)
        try:
            if filename.lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(file_like)
            else:
                df = pd.read_csv(file_like, dtype=str)
        except Exception as exc:
            raise ValueError(f"Could not parse file '{filename}': {exc}") from exc

        # Normalise column names
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        column_map = {col: COLUMN_ALIASES[col] for col in df.columns if col in COLUMN_ALIASES}

        if not column_map:
            raise ValueError(
                f"No recognised columns found. Got: {list(df.columns)}. "
                f"Expected at least one of: {list(COLUMN_ALIASES.keys())}"
            )

        df = df.rename(columns=column_map)
        records: list[dict] = []

        for _, row in df.iterrows():
            row_dict = row.where(row.notna(), None).to_dict()
            profile = self._normalise_row(row_dict, default_platform)
            if profile:
                records.append(profile)

        log.info("CSV parse: %d rows → %d valid profiles", len(df), len(records))
        return records

    def _normalise_row(self, row: dict, default_platform: str) -> Optional[dict]:
        """Map a raw CSV row to the internal profile schema."""
        username = (row.get("username") or "").strip()
        platform = PLATFORM_ALIASES.get(
            (row.get("platform") or default_platform).strip().lower(),
            default_platform,
        )

        # If a URL is provided but no username, try to extract both
        profile_url = (row.get("profile_url") or "").strip()
        if profile_url and not username:
            detected = _detect_platform_from_url(profile_url)
            if detected:
                platform = detected
            username = _extract_slug_from_url(profile_url, platform)

        if not username:
            return None

        follower_count = _safe_int(row.get("follower_count"))
        following_count = _safe_int(row.get("following_count"))

        return {
            "platform": platform,
            "platform_user_id": f"manual_{platform}_{username}",
            "username": username.lower().lstrip("@"),
            "display_name": (row.get("display_name") or username).strip(),
            "bio": (row.get("bio") or "").strip()[:1000],
            "profile_image_url": row.get("profile_image_url"),
            "location_raw": (row.get("location_raw") or "").strip(),
            "follower_count": follower_count,
            "following_count": following_count,
            "tweet_count": None,
            "verified": False,
            "engagement_rate": None,
            "source_method": "manual",
            "last_collected": datetime.now(timezone.utc),
            # Extra fields for enrichment (not in SocialProfile, discarded on upsert)
            "_profile_url": profile_url,
            "_email": (row.get("email") or "").strip() or None,
            "_phone": (row.get("phone") or "").strip() or None,
        }

    # ── URL enrichment ────────────────────────────────────────────────────────

    def enrich_from_url(self, url: str) -> Optional[dict]:
        """Synchronous entry point — enriches a single URL via bot. Celery-compatible."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_enrich_url(url))
        finally:
            loop.close()

    def enrich_from_urls(self, urls: list[str]) -> list[dict]:
        """Synchronous bulk URL enrichment."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_enrich_urls(urls))
        finally:
            loop.close()

    async def _async_enrich_urls(self, urls: list[str]) -> list[dict]:
        results: list[dict] = []
        async with BotScraper(
            platform="manual", use_proxy=self.use_proxy, headless=self.headless
        ) as bot:
            for url in urls:
                try:
                    profile = await self._scrape_url(bot, url)
                    if profile:
                        results.append(profile)
                    await _random_delay(3000, 8000)
                except Exception as exc:
                    log.warning("URL enrichment failed for %s: %s", url, exc)
        return results

    async def _async_enrich_url(self, url: str) -> Optional[dict]:
        async with BotScraper(
            platform="manual", use_proxy=self.use_proxy, headless=self.headless
        ) as bot:
            return await self._scrape_url(bot, url)

    async def _scrape_url(self, bot: BotScraper, url: str) -> Optional[dict]:
        """Route a URL to the appropriate platform scraper."""
        platform = _detect_platform_from_url(url)
        if not platform:
            log.warning("Could not detect platform for URL: %s", url)
            return None

        slug = _extract_slug_from_url(url, platform)
        if not slug:
            return None

        if platform == "tiktok":
            from app.collectors.tiktok import TikTokCollector
            collector = TikTokCollector(use_proxy=self.use_proxy, headless=self.headless)
            results = await collector._async_collect([slug], max_profiles=1, videos_per_user=10)
            return results[0] if results else None

        if platform == "linkedin":
            from app.collectors.linkedin import LinkedInCollector
            collector = LinkedInCollector(use_proxy=self.use_proxy, headless=self.headless)
            results = await collector._async_collect([slug], max_profiles=1, posts_per_profile=5, profile_type="person")
            return results[0] if results else None

        if platform == "instagram":
            return await self._scrape_instagram_public(bot, url, slug)

        if platform in ("twitter", "facebook"):
            return await self._scrape_generic_og(bot, url, slug, platform)

        # For unsupported platforms, extract Open Graph metadata only
        return await self._scrape_generic_og(bot, url, slug, platform)

    async def _scrape_instagram_public(self, bot: BotScraper, url: str, slug: str) -> Optional[dict]:
        """Scrape an Instagram public profile page."""
        page = await bot.new_page(inject_session=False)
        try:
            success = await bot.navigate(page, url)
            if not success:
                return None

            await _random_delay(2000, 4000)
            content = await page.content()

            # Extract from shared_data JSON embedded in page
            match = re.search(r'window\._sharedData\s*=\s*(\{.*?\});</script>', content, re.DOTALL)
            if match:
                try:
                    shared = json.loads(match.group(1))
                    user = shared.get("entry_data", {}).get("ProfilePage", [{}])[0].get(
                        "graphql", {}
                    ).get("user", {})
                    if user:
                        return {
                            "platform": "instagram",
                            "platform_user_id": str(user.get("id", f"ig_{slug}")),
                            "username": user.get("username", slug).lower(),
                            "display_name": user.get("full_name", slug),
                            "bio": user.get("biography", "")[:1000],
                            "profile_image_url": user.get("profile_pic_url_hd"),
                            "follower_count": user.get("edge_followed_by", {}).get("count", 0),
                            "following_count": user.get("edge_follow", {}).get("count", 0),
                            "tweet_count": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
                            "verified": user.get("is_verified", False),
                            "engagement_rate": None,
                            "location_raw": "",
                            "source_method": "bot",
                            "last_collected": datetime.now(timezone.utc),
                            "posts": [],
                        }
                except Exception:
                    pass

            # Fallback: Open Graph
            return await self._extract_og_meta(page, slug, "instagram")
        finally:
            await page.close()

    async def _scrape_generic_og(
        self, bot: BotScraper, url: str, slug: str, platform: str
    ) -> Optional[dict]:
        """Generic scraper using Open Graph meta tags."""
        page = await bot.new_page(inject_session=False)
        try:
            success = await bot.navigate(page, url)
            if not success:
                return None
            await _random_delay(1500, 3000)
            return await self._extract_og_meta(page, slug, platform)
        finally:
            await page.close()

    async def _extract_og_meta(self, page, slug: str, platform: str) -> dict:
        """Extract Open Graph / meta tag data as a minimal profile."""
        title = ""
        description = ""
        image = ""
        try:
            title = await page.title() or ""
        except Exception:
            pass
        try:
            desc_el = page.locator('meta[property="og:description"]').first
            if await desc_el.count() > 0:
                description = await desc_el.get_attribute("content") or ""
        except Exception:
            pass
        try:
            img_el = page.locator('meta[property="og:image"]').first
            if await img_el.count() > 0:
                image = await img_el.get_attribute("content") or ""
        except Exception:
            pass

        return {
            "platform": platform,
            "platform_user_id": f"{platform}_{slug}",
            "username": slug.lower().lstrip("@"),
            "display_name": title[:255] if title else slug,
            "bio": description[:1000],
            "profile_image_url": image or None,
            "follower_count": None,
            "following_count": None,
            "tweet_count": None,
            "verified": False,
            "engagement_rate": None,
            "location_raw": "",
            "source_method": "bot",
            "last_collected": datetime.now(timezone.utc),
            "posts": [],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def upsert_profiles(self, db: Session, profiles: list[dict]) -> int:
        """Bulk upsert a list of parsed profiles. Returns count of persisted profiles."""
        count = 0
        for profile_data in profiles:
            try:
                self.upsert_profile(db, profile_data)
                db.commit()
                count += 1
            except Exception as exc:
                log.warning("Failed to persist manual profile: %s", exc)
                db.rollback()
        return count

    def upsert_profile(self, db: Session, profile_data: dict) -> SocialProfile:
        """Upsert a single manually-imported profile."""
        # Strip internal-only fields
        profile_data.pop("_profile_url", None)
        profile_data.pop("_email", None)
        profile_data.pop("_phone", None)
        posts_data: list[dict] = profile_data.pop("posts", [])

        existing = (
            db.query(SocialProfile)
            .filter(
                SocialProfile.platform == profile_data["platform"],
                SocialProfile.platform_user_id == profile_data["platform_user_id"],
            )
            .first()
        )

        if existing:
            for key, val in profile_data.items():
                if hasattr(existing, key) and val is not None:
                    setattr(existing, key, val)
            profile = existing
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
