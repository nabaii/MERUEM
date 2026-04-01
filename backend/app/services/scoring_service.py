from __future__ import annotations

import math
from collections import Counter
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.cluster import Cluster
from app.db.models.post import Post
from app.db.models.profiling import LeadScore, ProfileAssessment
from app.db.models.social_profile import SocialProfile

DEFAULT_SCORING_WEIGHTS: dict[str, float] = {
    "purchase_intent": 0.30,
    "engagement_style": 0.15,
    "influence_tier": 0.10,
    "sentiment_alignment": 0.10,
    "follower_count": 0.10,
    "profile_completeness": 0.10,
    "cluster_quality": 0.10,
    "confidence_penalty": 0.05,
}

ENGAGEMENT_STYLE_SCORES = {
    "Creator": 100.0,
    "Amplifier": 80.0,
    "Commenter": 60.0,
    "Reactor": 40.0,
    "Lurker": 20.0,
}

INFLUENCE_TIER_SCORES = {
    "Macro": 100.0,
    "Mid": 80.0,
    "Micro": 60.0,
    "Nano": 40.0,
}

SENTIMENT_TONE_SCORES = {
    "Aspirational": 100.0,
    "Optimistic": 80.0,
    "Neutral": 50.0,
    "Frustrated": 30.0,
    "Cynical": 10.0,
}

CONFIDENCE_SCORES = {
    "High": 100.0,
    "Medium": 60.0,
    "Low": 20.0,
    "Insufficient Data": 0.0,
}


def assign_tier(score: float) -> str:
    if score >= 80:
        return "Hot"
    if score >= 60:
        return "Warm"
    if score >= 40:
        return "Cool"
    return "Cold"


def _purchase_intent_score(assessment: ProfileAssessment) -> float:
    if assessment.purchase_intent_score is None:
        return 0.0
    return max(0.0, min(100.0, float(assessment.purchase_intent_score) * 10.0))


def _follower_count_score(profile: SocialProfile) -> float:
    followers = max(profile.follower_count or 0, 0)
    if followers <= 0:
        return 0.0
    return min(100.0, (math.log10(followers) / math.log10(1_000_000)) * 100.0)


def _profile_completeness_score(profile: SocialProfile, post_count: int) -> float:
    score = 0.0
    if (profile.bio or "").strip():
        score += 25.0
    if (profile.location_raw or profile.location_inferred or "").strip():
        score += 25.0
    if post_count >= 5:
        score += 25.0
    if profile.embedding is not None:
        score += 25.0
    return score


def _cluster_quality_score(cluster: Cluster | None) -> float:
    if cluster is None:
        return 20.0
    member_count = max(cluster.member_count or 0, 1)
    # The current schema does not persist HDBSCAN density, so use cluster size as a density proxy.
    return min(100.0, 20.0 + (math.log10(member_count + 1) / math.log10(101)) * 80.0)


class ScoringService:
    def calculate_score(
        self,
        db: Session,
        assessment: ProfileAssessment,
        *,
        weights: dict[str, float] | None = None,
    ) -> tuple[float, dict[str, Any]]:
        weights = {**DEFAULT_SCORING_WEIGHTS, **(weights or {})}
        profile = db.get(SocialProfile, assessment.social_profile_id)
        if not profile:
            raise ValueError(f"Profile {assessment.social_profile_id} not found")

        post_count = (
            db.query(Post)
            .filter(Post.profile_id == assessment.social_profile_id)
            .count()
        )
        cluster = db.get(Cluster, profile.cluster_id) if profile.cluster_id is not None else None

        factor_scores = {
            "purchase_intent": _purchase_intent_score(assessment),
            "engagement_style": ENGAGEMENT_STYLE_SCORES.get(assessment.engagement_style or "", 0.0),
            "influence_tier": INFLUENCE_TIER_SCORES.get(assessment.influence_tier or "", 0.0),
            "sentiment_alignment": SENTIMENT_TONE_SCORES.get(assessment.sentiment_tone or "", 0.0),
            "follower_count": _follower_count_score(profile),
            "profile_completeness": _profile_completeness_score(profile, post_count),
            "cluster_quality": _cluster_quality_score(cluster),
            "confidence_penalty": CONFIDENCE_SCORES.get(assessment.confidence or "", 0.0),
        }

        total_weight = sum(weights.values()) or 1.0
        weighted_total = sum(factor_scores[name] * weights[name] for name in weights)
        total_score = max(0.0, min(100.0, weighted_total / total_weight))

        breakdown: dict[str, Any] = {
            name: {
                "score": round(factor_scores[name], 4),
                "weight": round(weights[name], 4),
                "weighted_score": round(factor_scores[name] * weights[name], 4),
            }
            for name in weights
        }
        breakdown["normalization_weight"] = round(total_weight, 4)
        breakdown["total_score"] = round(total_score, 4)

        return round(total_score, 4), breakdown

    def upsert_score(
        self,
        db: Session,
        assessment: ProfileAssessment,
        *,
        weights: dict[str, float] | None = None,
    ) -> LeadScore:
        total_score, breakdown = self.calculate_score(db, assessment, weights=weights)
        existing = (
            db.query(LeadScore)
            .filter(LeadScore.assessment_id == assessment.id)
            .first()
        )
        if existing:
            existing.total_score = total_score
            existing.score_breakdown = breakdown
            existing.tier = assign_tier(total_score)
            existing.target_industries = assessment.industry_fit or []
            db.add(existing)
            db.flush()
            return existing

        lead_score = LeadScore(
            social_profile_id=assessment.social_profile_id,
            assessment_id=assessment.id,
            total_score=total_score,
            score_breakdown=breakdown,
            tier=assign_tier(total_score),
            target_industries=assessment.industry_fit or [],
        )
        db.add(lead_score)
        db.flush()
        return lead_score

    def recalculate_all_scores(
        self,
        db: Session,
        *,
        weights: dict[str, float] | None = None,
    ) -> int:
        assessments = db.query(ProfileAssessment).all()
        recalculated = 0
        for assessment in assessments:
            self.upsert_score(db, assessment, weights=weights)
            recalculated += 1
        return recalculated

    def top_industries_from_latest_scores(
        self,
        latest_rows: list[tuple[LeadScore, ProfileAssessment, SocialProfile]],
    ) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for _, assessment, _ in latest_rows:
            counter.update(assessment.industry_fit or [])
        return dict(counter.most_common(10))

    def average_score(self, rows: list[LeadScore]) -> float | None:
        if not rows:
            return None
        return round(mean(score.total_score for score in rows), 4)
