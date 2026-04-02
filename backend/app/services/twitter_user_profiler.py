from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from statistics import mean
from typing import Any, Callable

import httpx

from app.core.config import settings
from app.prompts.twitter_user_profiling import (
    STRICT_JSON_ONLY_SUFFIX,
    TWITTER_USER_PROFILING_SYSTEM_PROMPT,
    TWITTER_USER_PROFILING_USER_TEMPLATE,
)
from app.schemas.discovery import DiscoveredTweet, DiscoveredUser, PublicContactInfo

log = logging.getLogger(__name__)

HYBRID_CORE_TERMS = [
    "hybrid",
    "hybrid car",
    "hybrid vehicle",
    "electric car",
    "electric vehicle",
    "ev",
    "fuel saving",
    "fuel saver",
    "fuel economy",
    "fuel efficiency",
    "battery",
    "charging",
    "commute",
    "traffic",
    "petrol",
    "fuel price",
    "transport cost",
    "maintenance cost",
    "toyota hybrid",
    "prius",
    "camry hybrid",
    "corolla cross",
    "rav4 hybrid",
]

HIGH_INTENT_TERMS = [
    "want to buy",
    "looking to buy",
    "considering buying",
    "should i buy",
    "need a car",
    "next car",
    "worth it",
    "affordable car",
    "budget car",
    "fuel saving",
    "save on fuel",
    "cost to maintain",
    "maintenance cost",
    "car recommendation",
    "best car",
    "dealership",
    "financing",
    "installment",
]

PAIN_POINT_TERMS = [
    "fuel price",
    "petrol",
    "subsidy",
    "traffic",
    "commute",
    "transport cost",
    "maintenance",
    "car trouble",
    "fuel queue",
    "ride fare",
    "uber",
    "bolt",
]

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
HANDLE_PATTERN = re.compile(r"(?<!\w)@[a-z0-9_\.]{2,30}", re.IGNORECASE)
URL_PATTERN = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)


class TwitterUserProfiler:
    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self.timeout = settings.anthropic_timeout_seconds

    def enrich_users(
        self,
        users: list[DiscoveredUser],
        *,
        keywords: list[str],
        target_location: str,
        fetch_recent_tweets: Callable[[str, int], list[dict[str, Any]]],
    ) -> list[DiscoveredUser]:
        if not users:
            return users

        llm_candidates: list[dict[str, Any]] = []

        for user in users:
            recent_raw = fetch_recent_tweets(user.platform_user_id, 10) or []
            recent_tweets = [self._tweet_from_api(tweet) for tweet in recent_raw[:10]]
            if not recent_tweets:
                recent_tweets = list(user.matching_tweets[:10])

            user.user_id = user.user_id or user.platform_user_id
            user.last_10_tweets = recent_tweets
            user.public_contact_info = self._extract_contact_info(user.bio or "")

            metrics = self._calculate_metrics(
                user,
                recent_raw=recent_raw[:10],
                recent_tweets=recent_tweets,
                keywords=keywords,
                target_location=target_location,
            )
            user.engagement_frequency_score = metrics["engagement_frequency_score"]
            user.topic_relevance_score = metrics["topic_relevance_score"]
            user.conversation_influence_score = metrics["conversation_influence_score"]
            user.conversion_likelihood_score = metrics["conversion_likelihood_score"]
            user.high_value_score = metrics["high_value_score"]
            user.high_value_band = metrics["high_value_band"]
            user.hybrid_signals = metrics["hybrid_signals"]
            user.actionable_insights = metrics["actionable_insights"]
            user.recommended_angle = metrics["recommended_angle"]
            user.user_type = self._fallback_user_type(user)

            llm_candidates.append(self._build_llm_candidate(user))

        self._apply_llm_labels(users, llm_candidates)
        users.sort(
            key=lambda item: (
                item.high_value_score,
                item.topic_relevance_score,
                item.location_match,
                item.relevance_score,
            ),
            reverse=True,
        )
        return users

    def _calculate_metrics(
        self,
        user: DiscoveredUser,
        *,
        recent_raw: list[dict[str, Any]],
        recent_tweets: list[DiscoveredTweet],
        keywords: list[str],
        target_location: str,
    ) -> dict[str, Any]:
        keyword_terms = [term.strip().lower() for term in keywords if term.strip()]
        combined_text = " ".join(
            part
            for part in [
                user.bio or "",
                " ".join(tweet.content or "" for tweet in user.matching_tweets),
                " ".join(tweet.content or "" for tweet in recent_tweets),
            ]
            if part
        ).lower()

        matched_keywords = self._unique_matches(combined_text, keyword_terms)
        matched_hybrid_terms = self._unique_matches(combined_text, HYBRID_CORE_TERMS)
        matched_intent_terms = self._unique_matches(combined_text, HIGH_INTENT_TERMS)
        matched_pain_points = self._unique_matches(combined_text, PAIN_POINT_TERMS)

        hybrid_signals = self._build_signal_labels(
            matched_keywords=matched_keywords,
            matched_hybrid_terms=matched_hybrid_terms,
            matched_intent_terms=matched_intent_terms,
            matched_pain_points=matched_pain_points,
            target_location=target_location,
            location_match=user.location_match,
        )

        engagement_frequency_score = self._engagement_frequency_score(user, recent_raw)
        conversation_influence_score = self._conversation_influence_score(user, recent_tweets)
        topic_relevance_score = round(
            min(
                100.0,
                len(matched_keywords) * 14.0
                + len(matched_hybrid_terms) * 10.0
                + len(matched_intent_terms) * 12.0
                + (12.0 if self._bio_has_topic_signal(user.bio or "", keyword_terms) else 0.0)
                + (6.0 if user.location_match else 0.0),
            ),
            2,
        )

        contact_score = self._contactability_score(user.public_contact_info)
        location_score = 100.0 if user.location_match else (40.0 if (user.location_raw or "").strip() else 0.0)
        behavior_score = round((engagement_frequency_score + conversation_influence_score) / 2.0, 2)
        intent_score = min(
            100.0,
            len(matched_intent_terms) * 22.0 + len(matched_pain_points) * 14.0,
        )

        conversion_likelihood_score = round(
            (
                topic_relevance_score * 0.35
                + intent_score * 0.25
                + contact_score * 0.15
                + location_score * 0.10
                + behavior_score * 0.15
            ),
            2,
        )
        high_value_score = round(
            (
                engagement_frequency_score * 0.25
                + topic_relevance_score * 0.30
                + conversation_influence_score * 0.20
                + conversion_likelihood_score * 0.25
            ),
            2,
        )

        return {
            "engagement_frequency_score": engagement_frequency_score,
            "topic_relevance_score": topic_relevance_score,
            "conversation_influence_score": conversation_influence_score,
            "conversion_likelihood_score": conversion_likelihood_score,
            "high_value_score": high_value_score,
            "high_value_band": self._high_value_band(high_value_score),
            "hybrid_signals": hybrid_signals,
            "actionable_insights": self._fallback_actionable_insights(
                user=user,
                hybrid_signals=hybrid_signals,
                contact_score=contact_score,
                influence_score=conversation_influence_score,
            ),
            "recommended_angle": self._fallback_recommended_angle(
                user=user,
                hybrid_signals=hybrid_signals,
            ),
        }

    def _engagement_frequency_score(
        self,
        user: DiscoveredUser,
        recent_raw: list[dict[str, Any]],
    ) -> float:
        joined_at = self._parse_datetime(user.date_joined_twitter)
        account_age_days = max((datetime.now(timezone.utc) - joined_at).days, 1) if joined_at else 365
        tweets_per_month = (user.tweet_count or 0) / max(account_age_days / 30.0, 1.0)
        monthly_score = min(100.0, (tweets_per_month / 60.0) * 100.0)

        recent_30d = 0
        conversation_posts = 0
        for tweet in recent_raw:
            created_at = self._parse_datetime(tweet.get("created_at"))
            if created_at and (datetime.now(timezone.utc) - created_at).days <= 30:
                recent_30d += 1
            if self._tweet_post_type(tweet) == "reply":
                conversation_posts += 1

        recent_score = min(100.0, (recent_30d / 10.0) * 100.0)
        conversation_score = (
            min(100.0, (conversation_posts / max(len(recent_raw), 1)) * 100.0)
            if recent_raw
            else 0.0
        )
        return round(
            monthly_score * 0.30 + recent_score * 0.30 + conversation_score * 0.40,
            2,
        )

    def _conversation_influence_score(
        self,
        user: DiscoveredUser,
        recent_tweets: list[DiscoveredTweet],
    ) -> float:
        if not recent_tweets:
            return 0.0

        avg_reply_count = mean(tweet.replies for tweet in recent_tweets)
        avg_engagement = mean(
            tweet.likes + (tweet.retweets * 2) + (tweet.replies * 3)
            for tweet in recent_tweets
        )
        total_engagement = sum(
            tweet.likes + (tweet.retweets * 2) + (tweet.replies * 3)
            for tweet in recent_tweets
        )
        engagement_per_1k_followers = (
            (total_engagement / max(user.follower_count or 1, 1)) * 1000.0
        )

        reply_score = min(100.0, (avg_reply_count / 6.0) * 100.0)
        engagement_score = min(100.0, (avg_engagement / 40.0) * 100.0)
        efficiency_score = min(100.0, (engagement_per_1k_followers / 15.0) * 100.0)

        return round(
            reply_score * 0.40 + engagement_score * 0.35 + efficiency_score * 0.25,
            2,
        )

    def _build_signal_labels(
        self,
        *,
        matched_keywords: list[str],
        matched_hybrid_terms: list[str],
        matched_intent_terms: list[str],
        matched_pain_points: list[str],
        target_location: str,
        location_match: bool,
    ) -> list[str]:
        signals: list[str] = []
        if matched_keywords:
            signals.append("Actively discusses campaign keywords")
        if matched_hybrid_terms:
            signals.append("Shows clear hybrid or fuel-efficiency relevance")
        if matched_pain_points:
            signals.append("Mentions transport or fuel pain points")
        if matched_intent_terms:
            signals.append("Exhibits buying or solution-seeking intent")
        if location_match:
            signals.append(f"Public profile aligns with target location ({target_location})")
        return signals[:4]

    def _fallback_actionable_insights(
        self,
        *,
        user: DiscoveredUser,
        hybrid_signals: list[str],
        contact_score: float,
        influence_score: float,
    ) -> list[str]:
        insights: list[str] = []
        if hybrid_signals:
            insights.append(hybrid_signals[0])
        if influence_score >= 60:
            insights.append("Worth prioritizing for reply-led engagement because their tweets attract conversation.")
        elif user.engagement_frequency_score >= 60:
            insights.append("Active enough to nurture through repeated public interactions and educational threads.")

        if contact_score >= 70:
            insights.append("Bio exposes a public contact path or external handle for follow-up beyond Twitter.")
        else:
            insights.append("No direct contact path in bio, so public conversation should be the first touchpoint.")

        return insights[:3]

    def _fallback_recommended_angle(
        self,
        *,
        user: DiscoveredUser,
        hybrid_signals: list[str],
    ) -> str:
        profile_text = f"{user.bio or ''} {' '.join(hybrid_signals)}".lower()
        if any(term in profile_text for term in ("uber", "bolt", "logistics", "fleet", "driver")):
            return "Lead with fuel-cost reduction, uptime, and total cost of ownership for daily commercial driving."
        if any(term in profile_text for term in ("auto", "cars", "review", "motoring", "creator")):
            return "Lead with practical hybrid education, performance trade-offs, and real-world reliability."
        if any(term in profile_text for term in ("student", "graduate", "young")):
            return "Lead with affordability, fuel savings, and long-term running-cost relief."
        return "Lead with everyday fuel savings, lower running costs, and easier city commuting in Nigeria."

    def _fallback_user_type(self, user: DiscoveredUser) -> str:
        text = f"{user.bio or ''} {' '.join(tweet.content for tweet in user.last_10_tweets[:5])}".lower()
        if any(term in text for term in ("uber", "bolt", "driver", "ride-hailing", "rider")):
            return "Ride-Hailing Driver"
        if any(term in text for term in ("fleet", "logistics", "ceo", "founder", "business owner", "operations")):
            return "Business Owner / Fleet Decision Maker"
        if any(term in text for term in ("auto", "automotive", "cars", "motoring", "review")):
            if any(term in text for term in ("creator", "youtuber", "blogger", "reviewer")):
                return "Automotive Creator"
            return "Auto Enthusiast"
        if any(term in text for term in ("climate", "sustainability", "green", "clean energy")):
            return "Sustainability Advocate"
        if any(term in text for term in ("student", "campus", "undergrad", "graduate")):
            return "Student / Young Professional"
        if any(term in text for term in ("dealer", "reseller", "importer", "autos")):
            return "Dealer / Reseller"
        if any(term in text for term in ("fuel", "petrol", "cost", "budget", "transport")):
            return "Price-Sensitive Consumer"
        return "Commuter"

    def _apply_llm_labels(
        self,
        users: list[DiscoveredUser],
        llm_candidates: list[dict[str, Any]],
    ) -> None:
        if not settings.anthropic_api_key or not llm_candidates:
            return

        lookup = {user.platform_user_id: user for user in users}
        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": settings.anthropic_api_version,
            "content-type": "application/json",
        }

        for start in range(0, len(llm_candidates), 8):
            chunk = llm_candidates[start : start + 8]
            prompt = TWITTER_USER_PROFILING_USER_TEMPLATE.format(
                users_json=json.dumps(chunk, ensure_ascii=True),
            )
            try:
                response = httpx.post(
                    settings.anthropic_api_base,
                    headers=headers,
                    timeout=self.timeout,
                    json={
                        "model": self.model,
                        "max_tokens": 1200,
                        "temperature": 0.1,
                        "system": TWITTER_USER_PROFILING_SYSTEM_PROMPT,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"{prompt}\n\n{STRICT_JSON_ONLY_SUFFIX}",
                            }
                        ],
                    },
                )
                response.raise_for_status()
                raw_payload = response.json()
                raw_text = "\n".join(
                    block.get("text", "")
                    for block in raw_payload.get("content", [])
                    if block.get("type") == "text"
                ).strip()
                parsed = self._parse_llm_response(raw_text)
            except Exception as exc:
                log.warning("Twitter user profiling LLM fallback triggered: %s", exc)
                continue

            for item in parsed:
                platform_user_id = str(item.get("platform_user_id") or "")
                user = lookup.get(platform_user_id)
                if not user:
                    continue

                user_type = str(item.get("user_type") or "").strip()
                actionable_insights = item.get("actionable_insights") or []
                recommended_angle = str(item.get("recommended_angle") or "").strip()

                if user_type:
                    user.user_type = user_type
                if isinstance(actionable_insights, list):
                    cleaned = [str(insight).strip() for insight in actionable_insights if str(insight).strip()]
                    if cleaned:
                        user.actionable_insights = cleaned[:3]
                if recommended_angle:
                    user.recommended_angle = recommended_angle

    def _build_llm_candidate(self, user: DiscoveredUser) -> dict[str, Any]:
        sample_tweets = [
            {
                "created_at": tweet.created_at,
                "content": tweet.content[:220],
                "engagement": tweet.likes + tweet.retweets + tweet.replies,
            }
            for tweet in user.last_10_tweets[:3]
        ]
        return {
            "platform_user_id": user.platform_user_id,
            "username": user.username,
            "display_name": user.display_name,
            "bio": user.bio,
            "location_raw": user.location_raw,
            "follower_count": user.follower_count,
            "following_count": user.following_count,
            "tweet_count": user.tweet_count,
            "location_match": user.location_match,
            "topic_relevance_score": user.topic_relevance_score,
            "conversion_likelihood_score": user.conversion_likelihood_score,
            "high_value_score": user.high_value_score,
            "hybrid_signals": user.hybrid_signals,
            "sample_tweets": sample_tweets,
        }

    def _parse_llm_response(self, raw_text: str) -> list[dict[str, Any]]:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end < start:
            raise ValueError("No JSON array found in LLM response")
        payload = json.loads(cleaned[start : end + 1])
        if not isinstance(payload, list):
            raise ValueError("LLM response was not a list")
        return [item for item in payload if isinstance(item, dict)]

    def _extract_contact_info(self, bio: str) -> PublicContactInfo:
        emails = self._dedupe_preserve_order(match.lower() for match in EMAIL_PATTERN.findall(bio))
        raw_phones = PHONE_PATTERN.findall(bio)
        phone_numbers = []
        for phone in raw_phones:
            digits = re.sub(r"\D", "", phone)
            if 10 <= len(digits) <= 15:
                phone_numbers.append(phone.strip())

        handles = self._dedupe_preserve_order(match for match in HANDLE_PATTERN.findall(bio))
        urls = []
        for url in URL_PATTERN.findall(bio):
            urls.append(url if url.lower().startswith("http") else f"https://{url}")

        return PublicContactInfo(
            emails=emails,
            phone_numbers=self._dedupe_preserve_order(phone_numbers),
            social_handles=handles,
            urls=self._dedupe_preserve_order(urls),
        )

    def _contactability_score(self, contact_info: PublicContactInfo) -> float:
        if contact_info.emails or contact_info.phone_numbers:
            return 100.0
        if contact_info.urls or contact_info.social_handles:
            return 70.0
        return 0.0

    def _tweet_from_api(self, tweet: dict[str, Any]) -> DiscoveredTweet:
        metrics = tweet.get("public_metrics") or {}
        return DiscoveredTweet(
            tweet_id=str(tweet.get("id")),
            content=tweet.get("text", ""),
            created_at=self._format_datetime(tweet.get("created_at")),
            likes=metrics.get("like_count", 0),
            retweets=metrics.get("retweet_count", 0),
            replies=metrics.get("reply_count", 0),
            post_type=self._tweet_post_type(tweet),
        )

    def _tweet_post_type(self, tweet: dict[str, Any]) -> str:
        referenced = tweet.get("referenced_tweets") or []
        reference_types = {str(item.get("type")) for item in referenced if isinstance(item, dict)}
        if "replied_to" in reference_types:
            return "reply"
        if "quoted" in reference_types:
            return "quote"
        if "retweeted" in reference_types:
            return "retweet"
        return "tweet"

    def _bio_has_topic_signal(self, bio: str, keyword_terms: list[str]) -> bool:
        bio_lower = bio.lower()
        return any(term in bio_lower for term in keyword_terms + HYBRID_CORE_TERMS)

    def _unique_matches(self, text: str, terms: list[str]) -> list[str]:
        return [term for term in self._dedupe_preserve_order(terms) if term and term in text]

    def _high_value_band(self, score: float) -> str:
        if score >= 80:
            return "Very High"
        if score >= 65:
            return "High"
        if score >= 50:
            return "Medium"
        return "Low"

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _format_datetime(self, value: Any) -> str | None:
        parsed = self._parse_datetime(value)
        return parsed.isoformat() if parsed else (str(value) if value else None)

    def _dedupe_preserve_order(self, items: list[str] | Any) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            key = str(item).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(key)
        return output
