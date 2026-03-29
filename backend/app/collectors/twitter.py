"""Twitter / X API v2 collector.

Fetches user profiles and their recent tweets using app-only Bearer Token auth.
Implements exponential backoff on rate limit errors (HTTP 429).
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import tweepy

from app.collectors.storage import raw_storage
from app.core.config import settings
from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

log = logging.getLogger(__name__)

PLATFORM = "twitter"

# Fields to request from the users/lookup endpoint
USER_FIELDS = [
    "id",
    "name",
    "username",
    "description",
    "location",
    "public_metrics",
    "profile_image_url",
    "created_at",
]

# Fields to request from the tweets endpoint
TWEET_FIELDS = [
    "id",
    "text",
    "created_at",
    "public_metrics",
    "entities",
    "lang",
    "referenced_tweets",
]

MAX_RESULTS_PER_PAGE = 100  # maximum allowed by Twitter API v2


class TwitterCollector:
    def __init__(self) -> None:
        if not settings.twitter_bearer_token:
            raise RuntimeError(
                "TWITTER_BEARER_TOKEN is not set. "
                "Add it to .env before running a Twitter collection."
            )
        self._client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            wait_on_rate_limit=False,  # we handle backoff ourselves
            return_type=dict,
        )

    # ------------------------------------------------------------------ #
    # Public interface
    # ------------------------------------------------------------------ #

    def collect_from_usernames(
        self,
        seed_usernames: list[str],
        max_profiles: int = 1000,
        tweets_per_user: int = 50,
    ) -> list[dict]:
        """
        Starting from seed usernames, collect profiles and their tweets.
        Returns a list of parsed profile dicts (also written to DB by the caller).
        """
        collected: list[dict] = []
        queue = list(seed_usernames)
        seen: set[str] = set()

        while queue and len(collected) < max_profiles:
            batch = [u for u in queue[:100] if u not in seen]
            queue = queue[100:]
            if not batch:
                break

            users = self._fetch_users_by_username(batch)
            if not users:
                continue

            for user in users:
                if len(collected) >= max_profiles:
                    break
                username = user.get("username", "")
                if username in seen:
                    continue
                seen.add(username)

                tweets = self._fetch_recent_tweets(user["id"], max_results=tweets_per_user)
                parsed = self._parse_profile(user, tweets)
                collected.append(parsed)
                log.info("Collected @%s (%d tweets)", username, len(tweets))

        log.info("Collection complete — %d profiles", len(collected))
        return collected

    # ------------------------------------------------------------------ #
    # Twitter API calls with exponential backoff
    # ------------------------------------------------------------------ #

    def _fetch_users_by_username(self, usernames: list[str]) -> list[dict]:
        """Fetch up to 100 users by username in one request."""
        for attempt in range(5):
            try:
                response = self._client.get_users(
                    usernames=usernames,
                    user_fields=USER_FIELDS,
                )
                data = response.get("data") or []
                raw_storage.save(PLATFORM, f"users_batch_{uuid.uuid4().hex[:8]}", response)
                return data
            except tweepy.TooManyRequests:
                wait = 2**attempt * 15  # 15s, 30s, 60s, 120s, 240s
                log.warning("Rate limited fetching users — waiting %ds", wait)
                time.sleep(wait)
            except tweepy.TweepyException as exc:
                log.error("Twitter API error fetching users: %s", exc)
                return []
        log.error("Giving up after 5 rate-limit retries for user batch")
        return []

    def _fetch_recent_tweets(self, user_id: str, max_results: int = 50) -> list[dict]:
        """Fetch the most recent tweets for a user_id."""
        tweets: list[dict] = []
        pagination_token: str | None = None

        while len(tweets) < max_results:
            remaining = min(max_results - len(tweets), MAX_RESULTS_PER_PAGE)
            for attempt in range(5):
                try:
                    response = self._client.get_users_tweets(
                        id=user_id,
                        max_results=min(remaining, 100),
                        tweet_fields=TWEET_FIELDS,
                        pagination_token=pagination_token,
                        exclude=["retweets"],
                    )
                    page_data: list[dict] = response.get("data") or []
                    tweets.extend(page_data)
                    raw_storage.save(
                        PLATFORM,
                        f"tweets_{user_id}_{uuid.uuid4().hex[:8]}",
                        response,
                    )
                    pagination_token = (
                        response.get("meta", {}).get("next_token")
                    )
                    break
                except tweepy.TooManyRequests:
                    wait = 2**attempt * 15
                    log.warning("Rate limited fetching tweets for %s — waiting %ds", user_id, wait)
                    time.sleep(wait)
                except tweepy.TweepyException as exc:
                    log.error("Twitter API error fetching tweets for %s: %s", user_id, exc)
                    return tweets

            if not pagination_token:
                break

        return tweets

    # ------------------------------------------------------------------ #
    # Parsing helpers
    # ------------------------------------------------------------------ #

    def _parse_profile(self, user: dict, tweets: list[dict]) -> dict:
        metrics: dict = user.get("public_metrics") or {}
        return {
            "platform": PLATFORM,
            "platform_user_id": str(user["id"]),
            "username": user.get("username"),
            "display_name": user.get("name"),
            "bio": user.get("description"),
            "profile_image_url": user.get("profile_image_url"),
            "location_raw": user.get("location"),
            "follower_count": metrics.get("followers_count"),
            "following_count": metrics.get("following_count"),
            "tweet_count": metrics.get("tweet_count"),
            "last_collected": datetime.now(timezone.utc).isoformat(),
            "tweets": [self._parse_tweet(t) for t in tweets],
        }

    @staticmethod
    def _parse_tweet(tweet: dict) -> dict:
        metrics: dict = tweet.get("public_metrics") or {}
        return {
            "platform_post_id": str(tweet["id"]),
            "content": tweet.get("text", ""),
            "post_type": "tweet",
            "likes": metrics.get("like_count"),
            "reposts": metrics.get("retweet_count"),
            "replies": metrics.get("reply_count"),
            "entities": tweet.get("entities"),
            "language": tweet.get("lang"),
            "posted_at": tweet.get("created_at"),
        }

    # ------------------------------------------------------------------ #
    # DB persistence helpers (called by Celery task)
    # ------------------------------------------------------------------ #

    def upsert_profile(self, db_session: Any, parsed: dict) -> SocialProfile:
        """Insert or update a SocialProfile row. Returns the model instance."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

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
            "platform",
            "platform_user_id",
            "username",
            "display_name",
            "bio",
            "profile_image_url",
            "location_raw",
            "follower_count",
            "following_count",
            "tweet_count",
        ):
            setattr(profile, field, parsed.get(field))

        profile.last_collected = datetime.now(timezone.utc)
        db_session.add(profile)
        db_session.flush()  # get profile.id without committing

        # Persist tweets
        for tweet_data in parsed.get("tweets", []):
            existing = (
                db_session.query(Post)
                .filter_by(platform_post_id=tweet_data["platform_post_id"])
                .first()
            )
            if existing:
                continue
            post = Post(
                id=uuid.uuid4(),
                profile_id=profile.id,
                **{k: v for k, v in tweet_data.items() if k != "posted_at"},
            )
            raw_posted_at = tweet_data.get("posted_at")
            if raw_posted_at:
                post.posted_at = (
                    datetime.fromisoformat(raw_posted_at.replace("Z", "+00:00"))
                    if isinstance(raw_posted_at, str)
                    else raw_posted_at
                )
            db_session.add(post)

        return profile
