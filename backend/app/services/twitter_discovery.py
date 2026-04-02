"""Twitter/X User Discovery service.

Orchestrates the full discovery pipeline:
1. Keyword expansion (via LLM)
2. Twitter Advanced Search (via Tweepy v2)
3. User deduplication & location-based prioritisation
"""

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import tweepy
except ModuleNotFoundError:
    tweepy = None

try:
    from app.collectors.storage import raw_storage
except ModuleNotFoundError:
    raw_storage = None
from app.core.config import settings
from app.schemas.discovery import (
    DiscoveredTweet,
    DiscoveredUser,
    DiscoveryResponse,
)
from app.services.twitter_user_profiler import TwitterUserProfiler

log = logging.getLogger(__name__)

PLATFORM = "twitter"

USER_FIELDS = [
    "id", "name", "username", "description", "location",
    "public_metrics", "profile_image_url", "created_at",
]

TWEET_FIELDS = [
    "id", "text", "created_at", "public_metrics",
    "author_id", "entities", "lang", "geo", "referenced_tweets",
]

NIGERIAN_LOCATION_HINTS = [
    "nigeria", "lagos", "abuja", "port harcourt", "kano", "ibadan",
    "kaduna", "benin city", "enugu", "owerri", "calabar", "warri",
    "uyo", "abeokuta", "jos", "ilorin", "ph", "naija",
]


class TwitterDiscoveryService:
    """Discovers Twitter users from keyword-based search."""

    def __init__(self, dummy_mode: bool = False) -> None:
        self._dummy_mode = dummy_mode
        self._client = None

        if self._dummy_mode:
            return

        if tweepy is None:
            raise RuntimeError(
                "tweepy is not installed. Install backend dependencies before running live Twitter discovery."
            )

        if not settings.twitter_bearer_token:
            raise RuntimeError(
                "TWITTER_BEARER_TOKEN is not set. "
                "Add it to .env before running Twitter discovery."
            )
        self._client = tweepy.Client(
            bearer_token=settings.twitter_bearer_token,
            wait_on_rate_limit=False,
            return_type=dict,
        )

    # ── Public interface ─────────────────────────────────────────────────

    def search_and_discover(
        self,
        keywords: list[str],
        location: str,
        since_date: Optional[str] = None,
        until_date: Optional[str] = None,
        max_results: int = 200,
    ) -> DiscoveryResponse:
        """Run the full discovery pipeline.

        Args:
            keywords: Combined list of seed + expanded keywords.
            location: Target location for prioritisation (e.g. "Nigeria").
            since_date: ISO date string (YYYY-MM-DD). Capped by API tier.
            until_date: ISO date string (YYYY-MM-DD).
            max_results: Max total tweets to fetch across all queries.

        Returns:
            DiscoveryResponse with discovered users sorted by relevance.
        """
        if self._dummy_mode:
            return self._build_dummy_discovery_response(
                keywords=keywords,
                location=location,
                max_results=max_results,
            )

        all_tweets: list[dict] = []
        tweets_per_query = max(10, max_results // max(len(keywords), 1))

        for keyword in keywords:
            query = self._build_query(keyword, location)
            tweets = self._search_tweets(
                query=query,
                max_results=min(tweets_per_query, 100),
                since_date=since_date,
                until_date=until_date,
            )
            all_tweets.extend(tweets)
            log.info("Query '%s' returned %d tweets", keyword, len(tweets))

            if len(all_tweets) >= max_results:
                break

        # Deduplicate tweets by ID
        seen_ids = set()
        unique_tweets = []
        for t in all_tweets:
            tid = t.get("id")
            if tid and tid not in seen_ids:
                seen_ids.add(tid)
                unique_tweets.append(t)

        log.info("Total unique tweets found: %d", len(unique_tweets))

        # Group tweets by author
        author_tweets = defaultdict(list)
        author_ids_set = set()
        for tweet in unique_tweets:
            author_id = tweet.get("author_id")
            if author_id:
                author_tweets[str(author_id)].append(tweet)
                author_ids_set.add(str(author_id))

        # Fetch user profiles for all authors
        author_ids = list(author_ids_set)
        users_map = self._fetch_users_by_id(author_ids)

        # Build discovered user objects with location scoring
        discovered_users = self._build_discovered_users(
            users_map, author_tweets, location
        )

        discovered_users = TwitterUserProfiler().enrich_users(
            discovered_users,
            keywords=keywords,
            target_location=location,
            fetch_recent_tweets=self._fetch_recent_tweets_for_user,
        )

        location_matched = sum(1 for u in discovered_users if u.location_match)
        high_value_users = sum(1 for u in discovered_users if u.high_value_score >= 65)

        return DiscoveryResponse(
            job_id=str(uuid.uuid4()),
            status="completed",
            dummy_mode=False,
            seed_keywords=[],  # filled by the caller
            expanded_keywords=keywords,
            location=location,
            users=discovered_users,
            total_tweets_scanned=len(unique_tweets),
            total_users_found=len(discovered_users),
            location_matched_count=location_matched,
            profiled_users_count=len(discovered_users),
            high_value_users_found=high_value_users,
        )

    def _build_dummy_discovery_response(
        self,
        keywords: list[str],
        location: str,
        max_results: int,
    ) -> DiscoveryResponse:
        generated_at = datetime.now(timezone.utc)
        keyword_pool = keywords or ["hybrid vehicle"]
        user_specs = [
            {
                "platform_user_id": "dummy-101",
                "username": "ridewithken",
                "display_name": "Ken Ride",
                "bio": "Uber driver in Lagos tracking fuel spend. Email: ken@ridewithken.ng",
                "location_raw": "Lagos, Nigeria",
                "follower_count": 4200,
                "following_count": 1180,
                "tweet_count": 18750,
                "date_joined_twitter": "2019-05-12T09:00:00+00:00",
                "user_type": "Ride-Hailing Driver",
                "public_contact_info": {
                    "emails": ["ken@ridewithken.ng"],
                    "phone_numbers": [],
                    "social_handles": ["@ridewithken_ig"],
                    "urls": ["https://ridewithken.ng"],
                },
                "engagement_frequency_score": 82,
                "topic_relevance_score": 91,
                "conversation_influence_score": 78,
                "conversion_likelihood_score": 88,
                "high_value_score": 85,
                "high_value_band": "High",
                "hybrid_signals": [
                    "Repeatedly talks about fuel savings on commercial routes.",
                    "Asks public questions about hybrid maintenance and uptime.",
                ],
                "actionable_insights": [
                    "Lead with daily operating-cost reduction for ride-hailing.",
                    "Offer proof around battery reliability in heavy city traffic.",
                ],
                "recommended_angle": "Frame the pitch around lower fuel burn across back-to-back ride-hailing shifts.",
                "tweet_templates": [
                    "{keyword} is the only thing making sense after another brutal fuel week in {location}.",
                    "Replying to drivers today because city traffic in {location} makes every litre count.",
                    "Passengers love AC, but fuel says no. I keep coming back to hybrid options.",
                    "If a hybrid can cut my weekly fuel bill, I will book a test drive immediately.",
                ],
                "base_likes": 24,
                "timeline_offset_days": 1,
            },
            {
                "platform_user_id": "dummy-102",
                "username": "fleetmamaada",
                "display_name": "Ada Fleet Mama",
                "bio": "School-run parent and small fleet operator. WhatsApp business in bio. IG: @fleetmamaada",
                "location_raw": "Abuja, Nigeria",
                "follower_count": 6900,
                "following_count": 960,
                "tweet_count": 12430,
                "date_joined_twitter": "2018-11-01T08:30:00+00:00",
                "user_type": "Family Fleet Manager",
                "public_contact_info": {
                    "emails": [],
                    "phone_numbers": [],
                    "social_handles": ["@fleetmamaada"],
                    "urls": ["https://wa.me/2348000000000"],
                },
                "engagement_frequency_score": 73,
                "topic_relevance_score": 86,
                "conversation_influence_score": 69,
                "conversion_likelihood_score": 80,
                "high_value_score": 77,
                "high_value_band": "High",
                "hybrid_signals": [
                    "Balances household mobility needs with operating cost.",
                    "Frequently compares hybrid ownership with conventional petrol cars.",
                ],
                "actionable_insights": [
                    "Position the car as a practical family-and-business crossover.",
                    "Share maintenance schedules and warranty reassurance.",
                ],
                "recommended_angle": "Focus on practical savings for family logistics and light fleet duty.",
                "tweet_templates": [
                    "I keep checking {keyword} because school runs and business errands are swallowing fuel.",
                    "Mums in {location} need cars that can idle in traffic without draining the budget.",
                    "Anyone here running a hybrid for family use and short delivery runs?",
                    "A reliable hybrid would solve two problems for me: fuel spend and constant mechanic visits.",
                ],
                "base_likes": 18,
                "timeline_offset_days": 2,
            },
            {
                "platform_user_id": "dummy-103",
                "username": "naijahybridtalks",
                "display_name": "Naija Hybrid Talks",
                "bio": "Auto creator breaking down hybrid ownership in plain English. YouTube and TikTok links below.",
                "location_raw": "Port Harcourt, Nigeria",
                "follower_count": 18500,
                "following_count": 740,
                "tweet_count": 9350,
                "date_joined_twitter": "2020-02-17T12:00:00+00:00",
                "user_type": "Automotive Creator",
                "public_contact_info": {
                    "emails": ["hello@naijahybridtalks.com"],
                    "phone_numbers": [],
                    "social_handles": ["@naijahybridtalks", "@naijahybridtalks_tiktok"],
                    "urls": [
                        "https://youtube.com/@naijahybridtalks",
                        "https://tiktok.com/@naijahybridtalks",
                    ],
                },
                "engagement_frequency_score": 88,
                "topic_relevance_score": 94,
                "conversation_influence_score": 84,
                "conversion_likelihood_score": 70,
                "high_value_score": 84,
                "high_value_band": "High",
                "hybrid_signals": [
                    "Educates followers about hybrid ownership and efficiency.",
                    "Reply threads regularly trigger follow-up questions from buyers.",
                ],
                "actionable_insights": [
                    "Strong candidate for creator-led educational partnerships.",
                    "Offer myth-busting content around battery life and resale value.",
                ],
                "recommended_angle": "Treat as a trusted educator who can translate technical benefits into buyer confidence.",
                "tweet_templates": [
                    "Every week I get DMs about {keyword}, so I am putting together another breakdown thread.",
                    "People in {location} still think hybrid ownership is complicated. It really is not.",
                    "Reply chains about running costs always outperform my basic car-news posts.",
                    "Show the savings math clearly and the audience leans in immediately.",
                ],
                "base_likes": 41,
                "timeline_offset_days": 0,
            },
            {
                "platform_user_id": "dummy-104",
                "username": "greenroutekunle",
                "display_name": "Green Route Kunle",
                "bio": "Logistics founder experimenting with cleaner, cheaper city delivery routes. Contact: kunle@greenroute.africa",
                "location_raw": "Lagos Mainland",
                "follower_count": 5300,
                "following_count": 640,
                "tweet_count": 8010,
                "date_joined_twitter": "2021-07-08T14:20:00+00:00",
                "user_type": "Logistics Founder",
                "public_contact_info": {
                    "emails": ["kunle@greenroute.africa"],
                    "phone_numbers": [],
                    "social_handles": ["@greenroute_africa"],
                    "urls": ["https://greenroute.africa"],
                },
                "engagement_frequency_score": 69,
                "topic_relevance_score": 83,
                "conversation_influence_score": 74,
                "conversion_likelihood_score": 79,
                "high_value_score": 76,
                "high_value_band": "High",
                "hybrid_signals": [
                    "Connects vehicle choice directly to route margin and uptime.",
                    "Openly tests alternatives to expensive petrol-heavy operations.",
                ],
                "actionable_insights": [
                    "Pitch hybrid adoption as an operating-margin lever for urban logistics.",
                    "Back claims with route-based case studies and running-cost tables.",
                ],
                "recommended_angle": "Lead with fleet economics, uptime, and lower stop-start fuel waste.",
                "tweet_templates": [
                    "Stop-start delivery routes are why {keyword} keeps coming up in our ops meetings.",
                    "If your van spends half the day in traffic, efficiency matters more than brochure horsepower.",
                    "Founders in {location} should compare route margins, not just sticker price.",
                    "The replies on my fuel-cost posts show how urgent this conversation has become.",
                ],
                "base_likes": 16,
                "timeline_offset_days": 3,
            },
            {
                "platform_user_id": "dummy-105",
                "username": "commuterkemi",
                "display_name": "Commuter Kemi",
                "bio": "Daily commuter sharing transport hacks, budgeting tips, and lighter city mobility options.",
                "location_raw": "Ibadan, Nigeria",
                "follower_count": 2100,
                "following_count": 890,
                "tweet_count": 6030,
                "date_joined_twitter": "2022-01-19T11:45:00+00:00",
                "user_type": "Urban Commuter",
                "public_contact_info": {
                    "emails": [],
                    "phone_numbers": [],
                    "social_handles": ["@commuterkemi"],
                    "urls": [],
                },
                "engagement_frequency_score": 64,
                "topic_relevance_score": 75,
                "conversation_influence_score": 58,
                "conversion_likelihood_score": 71,
                "high_value_score": 67,
                "high_value_band": "High",
                "hybrid_signals": [
                    "Publicly documents pain points around commuting costs.",
                    "Responds well to practical ownership stories and budgeting tips.",
                ],
                "actionable_insights": [
                    "Use relatable commuting scenarios instead of technical specs.",
                    "Show monthly budget impact and cabin comfort during traffic.",
                ],
                "recommended_angle": "Speak to daily comfort and predictable monthly transport costs.",
                "tweet_templates": [
                    "Commuting budgets are upside down again, so yes, I am reading every post about {keyword}.",
                    "{location} traffic drains energy and fuel. Efficient cars feel less optional every month.",
                    "If anyone has a simple hybrid ownership story, I want to hear it.",
                    "The best replies are always from people explaining real-world savings, not generic ads.",
                ],
                "base_likes": 11,
                "timeline_offset_days": 4,
            },
            {
                "platform_user_id": "dummy-106",
                "username": "abujatechzara",
                "display_name": "Zara Moves",
                "bio": "Tech community builder curious about mobility, cleaner cities, and smart consumer choices.",
                "location_raw": "Abuja Tech Corridor",
                "follower_count": 9700,
                "following_count": 1210,
                "tweet_count": 14110,
                "date_joined_twitter": "2017-09-03T10:15:00+00:00",
                "user_type": "Community Builder",
                "public_contact_info": {
                    "emails": ["zara@moves.community"],
                    "phone_numbers": [],
                    "social_handles": ["@zaramoves", "@zara_moves_ig"],
                    "urls": ["https://moves.community"],
                },
                "engagement_frequency_score": 77,
                "topic_relevance_score": 72,
                "conversation_influence_score": 81,
                "conversion_likelihood_score": 63,
                "high_value_score": 73,
                "high_value_band": "Medium",
                "hybrid_signals": [
                    "Brings a credible community lens and sparks comment threads.",
                    "Less transactional, but influential among curious early adopters.",
                ],
                "actionable_insights": [
                    "Pair with educational community events or test-drive roundtables.",
                    "Use social proof and city-livability messaging over direct sales copy.",
                ],
                "recommended_angle": "Position hybrid adoption as a smart-city and quality-of-life decision.",
                "tweet_templates": [
                    "Mobility conversations in our community keep circling back to {keyword}.",
                    "People in {location} want smarter transport choices, but they also want clarity.",
                    "A good explainer thread can move more minds than a hard-sell launch post.",
                    "When replies turn into debates, you know the market is ready for better education.",
                ],
                "base_likes": 22,
                "timeline_offset_days": 5,
            },
        ]

        user_count = max(3, min(len(user_specs), max_results // 30 + 2))
        selected_specs = user_specs[:user_count]
        users = [
            self._build_dummy_user(
                spec=spec,
                keywords=keyword_pool,
                target_location=location,
                generated_at=generated_at,
            )
            for spec in selected_specs
        ]
        users.sort(key=lambda user: (user.high_value_score, user.relevance_score), reverse=True)

        location_matched = sum(1 for user in users if user.location_match)
        high_value_users = sum(1 for user in users if user.high_value_score >= 65)
        simulated_tweets_scanned = min(max_results, max(24, len(users) * 14))

        return DiscoveryResponse(
            job_id=str(uuid.uuid4()),
            status="completed",
            dummy_mode=True,
            seed_keywords=[],
            expanded_keywords=keywords,
            location=location,
            users=users,
            total_tweets_scanned=simulated_tweets_scanned,
            total_users_found=len(users),
            location_matched_count=location_matched,
            profiled_users_count=len(users),
            high_value_users_found=high_value_users,
            selected_micro_influencers=[],
        )

    # ── Twitter search ───────────────────────────────────────────────────

    def _build_query(self, keyword: str, location: str) -> str:
        """Build a Twitter v2 search query with location context.

        Uses Twitter advanced search operators:
        - The keyword itself
        - `-is:retweet` to exclude retweets (focus on original content)
        - `lang:en` for English content
        - Location terms are added to the query for better results
        """
        # Wrap multi-word keywords in quotes
        kw = f'"{keyword}"' if " " in keyword else keyword

        # Build query — Twitter v2 doesn't support `near:` operator,
        # so we add location as an additional keyword to bias results.
        # Location filtering is done post-search via user profile data.
        query = f"{kw} -is:retweet lang:en"

        # Cap query length at 512 chars (Twitter limit)
        if len(query) > 512:
            query = query[:512]

        return query

    def _search_tweets(
        self,
        query: str,
        max_results: int = 100,
        since_date: Optional[str] = None,
        until_date: Optional[str] = None,
    ) -> list[dict]:
        """Search recent tweets using Twitter API v2.

        The free/Basic tier uses `search_recent_tweets` (7-day window).
        Upgrade path: swap to `client.search_all_tweets()` for full archive.
        """
        all_tweets: list[dict] = []
        next_token: Optional[str] = None

        while len(all_tweets) < max_results:
            remaining = min(max_results - len(all_tweets), 100)
            # Twitter v2 requires min 10 results per call
            remaining = max(remaining, 10)

            for attempt in range(5):
                try:
                    kwargs: dict = {
                        "query": query,
                        "max_results": remaining,
                        "tweet_fields": TWEET_FIELDS,
                        "user_fields": USER_FIELDS,
                        "expansions": ["author_id"],
                    }
                    if next_token:
                        kwargs["next_token"] = next_token

                    # Use search_recent_tweets (7-day window, Basic tier)
                    # To use full archive: self._client.search_all_tweets(**kwargs)
                    response = self._client.search_recent_tweets(**kwargs)

                    page_data = response.get("data") or []
                    all_tweets.extend(page_data)

                    if raw_storage is not None:
                        raw_storage.save(
                            PLATFORM,
                            f"discovery_search_{uuid.uuid4().hex[:8]}",
                            response,
                        )

                    next_token = response.get("meta", {}).get("next_token")
                    break

                except tweepy.TooManyRequests:
                    wait = 2 ** attempt * 15
                    log.warning("Rate limited on search — waiting %ds", wait)
                    time.sleep(wait)
                except tweepy.TweepyException as exc:
                    log.error("Twitter search error: %s", exc)
                    return all_tweets

            if not next_token:
                break

        return all_tweets

    def _fetch_users_by_id(self, user_ids: list[str]) -> dict[str, dict]:
        """Fetch user profiles by their IDs. Returns {user_id: user_data}."""
        users_map: dict[str, dict] = {}

        # Twitter allows max 100 users per request
        for i in range(0, len(user_ids), 100):
            batch = user_ids[i : i + 100]
            for attempt in range(5):
                try:
                    response = self._client.get_users(
                        ids=batch,
                        user_fields=USER_FIELDS,
                    )
                    data = response.get("data") or []
                    for user in data:
                        users_map[str(user["id"])] = user
                    break
                except tweepy.TooManyRequests:
                    wait = 2 ** attempt * 15
                    log.warning("Rate limited fetching users — waiting %ds", wait)
                    time.sleep(wait)
                except tweepy.TweepyException as exc:
                    log.error("Error fetching users: %s", exc)
                    break

        return users_map

    def _fetch_recent_tweets_for_user(
        self,
        user_id: str,
        max_results: int = 10,
    ) -> list[dict]:
        tweets: list[dict] = []
        pagination_token: Optional[str] = None

        while len(tweets) < max_results:
            remaining = min(max_results - len(tweets), 100)
            for attempt in range(5):
                try:
                    response = self._client.get_users_tweets(
                        id=user_id,
                        max_results=max(5, remaining),
                        tweet_fields=TWEET_FIELDS,
                        pagination_token=pagination_token,
                        exclude=["retweets"],
                    )
                    page_data = response.get("data") or []
                    tweets.extend(page_data)
                    if raw_storage is not None:
                        raw_storage.save(
                            PLATFORM,
                            f"discovery_recent_tweets_{user_id}_{uuid.uuid4().hex[:8]}",
                            response,
                        )
                    pagination_token = response.get("meta", {}).get("next_token")
                    break
                except tweepy.TooManyRequests:
                    wait = 2 ** attempt * 15
                    log.warning("Rate limited fetching recent tweets for %s - waiting %ds", user_id, wait)
                    time.sleep(wait)
                except tweepy.TweepyException as exc:
                    log.error("Error fetching recent tweets for %s: %s", user_id, exc)
                    return tweets

            if not pagination_token:
                break

        return tweets[:max_results]

    # ── Result building ──────────────────────────────────────────────────

    def _build_discovered_users(
        self,
        users_map: dict[str, dict],
        author_tweets: dict[str, list[dict]],
        target_location: str,
    ) -> list[DiscoveredUser]:
        """Build DiscoveredUser objects with location matching and relevance scoring."""
        discovered = []

        for user_id, tweets in author_tweets.items():
            user = users_map.get(user_id)
            if not user:
                continue

            metrics = user.get("public_metrics") or {}
            location_match = self._location_matches(
                user.get("location"),
                target_location,
            )

            # Relevance score: combination of engagement + tweet count + location
            total_engagement = 0
            matching_tweets = []
            for tweet in tweets:
                tm = tweet.get("public_metrics") or {}
                engagement = (
                    tm.get("like_count", 0)
                    + tm.get("retweet_count", 0) * 2  # reposts weighted higher
                    + tm.get("reply_count", 0) * 3     # replies weighted highest
                )
                total_engagement += engagement

                matching_tweets.append(
                    DiscoveredTweet(
                        tweet_id=str(tweet["id"]),
                        content=tweet.get("text", ""),
                        created_at=tweet.get("created_at"),
                        likes=tm.get("like_count", 0),
                        retweets=tm.get("retweet_count", 0),
                        replies=tm.get("reply_count", 0),
                        post_type=self._tweet_post_type(tweet),
                    )
                )

            # Score formula: tweets * engagement * location_bonus
            relevance_score = (
                len(tweets) * 10
                + total_engagement
                + (100 if location_match else 0)
            )

            discovered.append(
                DiscoveredUser(
                    platform_user_id=str(user["id"]),
                    user_id=str(user["id"]),
                    username=user.get("username", ""),
                    display_name=user.get("name"),
                    bio=user.get("description"),
                    location_raw=user.get("location"),
                    profile_image_url=user.get("profile_image_url"),
                    follower_count=metrics.get("followers_count", 0),
                    following_count=metrics.get("following_count", 0),
                    tweet_count=metrics.get("tweet_count", 0),
                    location_match=location_match,
                    relevance_score=relevance_score,
                    matching_tweets=matching_tweets,
                    date_joined_twitter=self._format_datetime(user.get("created_at")),
                )
            )

        return discovered

    def _build_dummy_user(
        self,
        spec: dict,
        keywords: list[str],
        target_location: str,
        generated_at: datetime,
    ) -> DiscoveredUser:
        last_10_tweets = self._build_dummy_timeline(
            username=spec["username"],
            tweet_templates=spec["tweet_templates"],
            keywords=keywords,
            location=target_location,
            generated_at=generated_at,
            base_likes=spec["base_likes"],
            offset_days=spec["timeline_offset_days"],
        )
        matching_tweets = last_10_tweets[:3]
        location_match = self._location_matches(spec["location_raw"], target_location)
        relevance_score = round(
            spec["topic_relevance_score"] * 0.45
            + spec["conversation_influence_score"] * 0.25
            + spec["conversion_likelihood_score"] * 0.2
            + len(matching_tweets) * 8
            + (12 if location_match else 0),
            1,
        )

        return DiscoveredUser(
            platform_user_id=spec["platform_user_id"],
            user_id=spec["platform_user_id"],
            username=spec["username"],
            display_name=spec["display_name"],
            bio=spec["bio"],
            location_raw=spec["location_raw"],
            profile_image_url=None,
            follower_count=spec["follower_count"],
            following_count=spec["following_count"],
            tweet_count=spec["tweet_count"],
            location_match=location_match,
            relevance_score=relevance_score,
            matching_tweets=matching_tweets,
            date_joined_twitter=spec["date_joined_twitter"],
            last_10_tweets=last_10_tweets,
            user_type=spec["user_type"],
            public_contact_info=spec["public_contact_info"],
            engagement_frequency_score=spec["engagement_frequency_score"],
            topic_relevance_score=spec["topic_relevance_score"],
            conversation_influence_score=spec["conversation_influence_score"],
            conversion_likelihood_score=spec["conversion_likelihood_score"],
            high_value_score=spec["high_value_score"],
            high_value_band=spec["high_value_band"],
            hybrid_signals=spec["hybrid_signals"],
            actionable_insights=spec["actionable_insights"],
            recommended_angle=spec["recommended_angle"],
        )

    def _build_dummy_timeline(
        self,
        username: str,
        tweet_templates: list[str],
        keywords: list[str],
        location: str,
        generated_at: datetime,
        base_likes: int,
        offset_days: int,
    ) -> list[DiscoveredTweet]:
        keyword_pool = keywords or ["hybrid vehicle"]
        timeline: list[DiscoveredTweet] = []

        for index in range(10):
            template = tweet_templates[index % len(tweet_templates)]
            keyword = keyword_pool[index % len(keyword_pool)]
            post_type = "reply" if index in {1, 4, 7} else "quote" if index in {3, 8} else "tweet"
            likes = base_likes + max(0, 12 - index * 2)
            retweets = max(1, base_likes // 8 + (index % 3))
            replies = max(1, base_likes // 10 + (2 if post_type == "reply" else 0) + (index % 2))
            created_at = generated_at - timedelta(days=offset_days + index, hours=index % 5)
            timeline.append(
                DiscoveredTweet(
                    tweet_id=f"{username}-dummy-{index + 1}",
                    content=template.format(keyword=keyword, location=location),
                    created_at=created_at.isoformat(),
                    likes=likes,
                    retweets=retweets,
                    replies=replies,
                    post_type=post_type,
                )
            )

        return timeline

    def _location_matches(
        self,
        user_location: str | None,
        target_location: str,
    ) -> bool:
        user_location_lower = (user_location or "").strip().lower()
        target_location_lower = (target_location or "").strip().lower()
        if not user_location_lower or not target_location_lower:
            return False
        if target_location_lower in user_location_lower:
            return True
        if target_location_lower == "nigeria":
            return any(loc in user_location_lower for loc in NIGERIAN_LOCATION_HINTS)
        return False

    def _tweet_post_type(self, tweet: dict) -> str:
        referenced = tweet.get("referenced_tweets") or []
        reference_types = {str(item.get("type")) for item in referenced if isinstance(item, dict)}
        if "replied_to" in reference_types:
            return "reply"
        if "quoted" in reference_types:
            return "quote"
        if "retweeted" in reference_types:
            return "retweet"
        return "tweet"

    def _format_datetime(self, value: str | None) -> str | None:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
