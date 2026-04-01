from __future__ import annotations

import json
import logging
import re
import time
from statistics import mean
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.cluster import Cluster
from app.db.models.post import Post
from app.db.models.profiling import ProfileAssessment
from app.db.models.profile_interest import ProfileInterest
from app.db.models.social_profile import SocialProfile
from app.prompts.profiling import (
    PROFILING_SYSTEM_PROMPT,
    PROFILING_USER_TEMPLATE,
    STRICT_JSON_SUFFIX,
)
from app.schemas.profiling import AssessmentPayload, ProfilingFilters

log = logging.getLogger(__name__)


class ProfilingServiceError(RuntimeError):
    """Base error raised by the profiling service."""


class ProfilingConfigurationError(ProfilingServiceError):
    """Raised when profiling is requested without required configuration."""


class ProfilingResponseError(ProfilingServiceError):
    """Raised when the upstream API returns unusable data."""


def select_profiles_for_profiling(
    db: Session,
    filters: ProfilingFilters,
    limit: int | None = None,
) -> list[UUID]:
    query = db.query(SocialProfile.id).filter(
        SocialProfile.embedding.is_not(None),
        SocialProfile.cluster_id.is_not(None),
    )

    if filters.platform:
        query = query.filter(SocialProfile.platform == filters.platform)
    if filters.cluster_id is not None:
        query = query.filter(SocialProfile.cluster_id == filters.cluster_id)
    if filters.location:
        query = query.filter(SocialProfile.location_inferred.ilike(f"%{filters.location}%"))
    if filters.min_followers is not None:
        query = query.filter(SocialProfile.follower_count >= filters.min_followers)
    if filters.unassessed_only:
        query = (
            query.outerjoin(
                ProfileAssessment,
                ProfileAssessment.social_profile_id == SocialProfile.id,
            )
            .filter(ProfileAssessment.id.is_(None))
        )

    query = query.order_by(SocialProfile.follower_count.desc(), SocialProfile.created_at.desc())
    if limit:
        query = query.limit(limit)
    return [row[0] for row in query.all()]


class ProfilingService:
    def __init__(self) -> None:
        self.model = settings.anthropic_model
        self.timeout = settings.anthropic_timeout_seconds

    def assess_profile(
        self,
        db: Session,
        social_profile_id: UUID,
        *,
        force: bool = True,
    ) -> ProfileAssessment:
        if not force:
            existing = (
                db.query(ProfileAssessment)
                .filter(ProfileAssessment.social_profile_id == social_profile_id)
                .order_by(ProfileAssessment.created_at.desc())
                .first()
            )
            if existing:
                return existing

        profile = db.get(SocialProfile, social_profile_id)
        if not profile:
            raise ProfilingServiceError(f"Profile {social_profile_id} not found")

        recent_posts = (
            db.query(Post)
            .filter(Post.profile_id == social_profile_id)
            .order_by(Post.posted_at.desc())
            .limit(8)
            .all()
        )
        cluster = db.get(Cluster, profile.cluster_id) if profile.cluster_id is not None else None
        interests = (
            db.query(ProfileInterest)
            .filter(ProfileInterest.profile_id == social_profile_id)
            .order_by(ProfileInterest.confidence.desc())
            .limit(5)
            .all()
        )

        if not (profile.bio or "").strip() and not any((post.content or "").strip() for post in recent_posts):
            assessment = self._create_insufficient_data_assessment(db, profile)
            db.add(assessment)
            db.flush()
            return assessment

        context = self._build_context(profile, recent_posts, cluster, interests)
        user_prompt = PROFILING_USER_TEMPLATE.format(**context)
        payload, raw_response = self._request_assessment(user_prompt)

        assessment = ProfileAssessment(
            social_profile_id=profile.id,
            unified_user_id=profile.unified_user_id,
            persona=payload.persona,
            primary_interests=payload.primary_interests,
            secondary_interests=payload.secondary_interests,
            sentiment_tone=payload.sentiment_tone,
            purchase_intent_score=payload.purchase_intent_score,
            influence_tier=payload.influence_tier,
            engagement_style=payload.engagement_style,
            psychographic_driver=payload.psychographic_driver,
            recommended_channel=payload.recommended_channel,
            recommended_message_angle=payload.recommended_message_angle,
            industry_fit=payload.industry_fit,
            confidence=payload.confidence,
            raw_llm_response=raw_response,
            model_used=self.model,
        )
        db.add(assessment)
        db.flush()
        return assessment

    def build_prompt_for_profile(self, db: Session, social_profile_id: UUID) -> str:
        profile = db.get(SocialProfile, social_profile_id)
        if not profile:
            raise ProfilingServiceError(f"Profile {social_profile_id} not found")
        recent_posts = (
            db.query(Post)
            .filter(Post.profile_id == social_profile_id)
            .order_by(Post.posted_at.desc())
            .limit(8)
            .all()
        )
        cluster = db.get(Cluster, profile.cluster_id) if profile.cluster_id is not None else None
        interests = (
            db.query(ProfileInterest)
            .filter(ProfileInterest.profile_id == social_profile_id)
            .order_by(ProfileInterest.confidence.desc())
            .limit(5)
            .all()
        )
        return PROFILING_USER_TEMPLATE.format(
            **self._build_context(profile, recent_posts, cluster, interests)
        )

    def parse_assessment_text(self, raw_text: str) -> AssessmentPayload:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ProfilingResponseError("No JSON object found in profiling response")
        return AssessmentPayload.model_validate_json(cleaned[start : end + 1])

    def _build_context(
        self,
        profile: SocialProfile,
        recent_posts: list[Post],
        cluster: Cluster | None,
        interests: list[ProfileInterest],
    ) -> dict[str, Any]:
        hashtags: list[str] = []
        entities: list[str] = []
        sentiments: list[float] = []

        for post in recent_posts:
            if post.sentiment_score is not None:
                sentiments.append(post.sentiment_score)
            post_entities = post.entities or {}
            hashtags.extend(post_entities.get("hashtags", []))
            entities.extend(post_entities.get("mentions", []))
            entities.extend(post_entities.get("urls", []))

        notable_hashtags = sorted({tag for tag in hashtags if tag})[:10]
        detected_entities = sorted({entity for entity in entities if entity})[:10]
        top_interests = [item.topic for item in interests if item.topic]
        if top_interests:
            detected_entities.extend([topic for topic in top_interests if topic not in detected_entities])

        formatted_posts = []
        for index, post in enumerate(recent_posts, 1):
            content = (post.content or "").strip().replace("\n", " ")
            if content:
                formatted_posts.append(f"{index}. {content[:280]}")
        if not formatted_posts:
            formatted_posts.append("1. No recent posts available.")

        avg_sentiment = round(mean(sentiments), 4) if sentiments else "unknown"
        return {
            "platform": profile.platform,
            "handle": profile.username or profile.platform_user_id,
            "display_name": profile.display_name or profile.username or "Unknown",
            "bio": profile.bio or "",
            "follower_count": profile.follower_count or 0,
            "following_count": profile.following_count or 0,
            "location_stated": profile.location_raw or "",
            "location_inferred": profile.location_inferred or "",
            "recent_posts_formatted": "\n".join(formatted_posts),
            "entities": ", ".join(detected_entities) or "none",
            "avg_sentiment": avg_sentiment,
            "cluster_label": cluster.label if cluster and cluster.label else "unclustered",
            "hashtags": ", ".join(notable_hashtags) or "none",
        }

    def _request_assessment(self, user_prompt: str) -> tuple[AssessmentPayload, str]:
        if not settings.anthropic_api_key:
            raise ProfilingConfigurationError("ANTHROPIC_API_KEY is not configured")

        headers = {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": settings.anthropic_api_version,
            "content-type": "application/json",
        }

        for attempt, delay in enumerate((2, 4, 8), start=1):
            try:
                response = httpx.post(
                    settings.anthropic_api_base,
                    headers=headers,
                    timeout=self.timeout,
                    json={
                        "model": self.model,
                        "max_tokens": 800,
                        "temperature": 0.2,
                        "system": PROFILING_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
            except httpx.TimeoutException as exc:
                if attempt == 3:
                    raise ProfilingResponseError("Anthropic request timed out") from exc
                time.sleep(delay)
                continue
            except httpx.HTTPError as exc:
                if attempt == 3:
                    raise ProfilingResponseError("Anthropic request failed") from exc
                time.sleep(delay)
                continue

            if response.status_code == 429:
                log.warning("Anthropic rate-limited profiling request; sleeping for 60s")
                time.sleep(60)
                continue

            if response.status_code >= 500:
                if attempt == 3:
                    raise ProfilingResponseError(
                        f"Anthropic server error: {response.status_code}"
                    )
                time.sleep(delay)
                continue

            response.raise_for_status()
            raw_payload = response.json()
            raw_text = "\n".join(
                block.get("text", "")
                for block in raw_payload.get("content", [])
                if block.get("type") == "text"
            ).strip()

            try:
                return self.parse_assessment_text(raw_text), json.dumps(raw_payload, default=str)
            except Exception:
                try:
                    strict_text = self._retry_strict_json(user_prompt, headers=headers)
                    return self.parse_assessment_text(strict_text), strict_text
                except Exception as exc:
                    raise ProfilingResponseError("Profiling response was not valid JSON") from exc

        raise ProfilingResponseError("Profiling request exceeded retry budget")

    def _retry_strict_json(self, user_prompt: str, *, headers: dict[str, str]) -> str:
        response = httpx.post(
            settings.anthropic_api_base,
            headers=headers,
            timeout=self.timeout,
            json={
                "model": self.model,
                "max_tokens": 800,
                "temperature": 0.2,
                "system": PROFILING_SYSTEM_PROMPT,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{user_prompt}\n\n{STRICT_JSON_SUFFIX}",
                    }
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        return "\n".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        ).strip()

    def _create_insufficient_data_assessment(
        self,
        db: Session,
        profile: SocialProfile,
    ) -> ProfileAssessment:
        return ProfileAssessment(
            social_profile_id=profile.id,
            unified_user_id=profile.unified_user_id,
            confidence="Insufficient Data",
            raw_llm_response="Skipped profiling because the profile has no bio and no recent posts.",
            model_used=self.model,
        )
