from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from app.db.models.cluster import Cluster
from app.db.models.post import Post
from app.db.models.profiling import ProfileAssessment
from app.db.models.social_profile import SocialProfile
from app.services.scoring_service import ScoringService, assign_tier


def test_scoring_service_calculates_expected_hot_score(db):
    cluster = Cluster(label="Fintech Builders", member_count=40, top_interests={"fintech": 12})
    db.add(cluster)
    db.flush()

    profile = SocialProfile(
        id=uuid.uuid4(),
        platform="twitter",
        platform_user_id="tw_score",
        username="scoreme",
        display_name="Score Me",
        bio="Operator building for Nigerian merchants",
        location_raw="Lagos",
        follower_count=10_000,
        following_count=500,
        cluster_id=cluster.id,
    )
    db.add(profile)
    db.flush()

    for idx in range(6):
        db.add(
            Post(
                id=uuid.uuid4(),
                profile_id=profile.id,
                platform_post_id=f"post-{idx}",
                content=f"Post {idx}",
                posted_at=datetime.now(timezone.utc),
            )
        )

    assessment = ProfileAssessment(
        id=uuid.uuid4(),
        social_profile_id=profile.id,
        persona="Hustling Professional",
        primary_interests=["fintech"],
        secondary_interests=["payments"],
        sentiment_tone="Optimistic",
        purchase_intent_score=8,
        influence_tier="Mid",
        engagement_style="Creator",
        psychographic_driver="Achievement",
        recommended_channel="LinkedIn",
        recommended_message_angle="Talk about faster revenue growth.",
        industry_fit=["Fintech"],
        confidence="High",
        model_used="claude-sonnet-4-20250514",
    )
    db.add(assessment)
    db.commit()

    total_score, breakdown = ScoringService().calculate_score(db, assessment)

    expected_cluster_quality = min(
        100.0,
        20.0 + (math.log10(cluster.member_count + 1) / math.log10(101)) * 80.0,
    )
    expected_total = (
        80.0 * 0.30
        + 100.0 * 0.15
        + 80.0 * 0.10
        + 80.0 * 0.10
        + ((math.log10(10_000) / math.log10(1_000_000)) * 100.0) * 0.10
        + 75.0 * 0.10
        + expected_cluster_quality * 0.10
        + 100.0 * 0.05
    )

    assert total_score == round(expected_total, 4)
    assert breakdown["purchase_intent"]["score"] == 80.0
    assert assign_tier(total_score) == "Hot"


def test_upsert_score_persists_target_industries(db):
    profile = SocialProfile(
        id=uuid.uuid4(),
        platform="twitter",
        platform_user_id="tw_upsert",
        username="upsertme",
        display_name="Upsert Me",
        follower_count=100,
        following_count=50,
    )
    assessment = ProfileAssessment(
        id=uuid.uuid4(),
        social_profile_id=profile.id,
        purchase_intent_score=5,
        industry_fit=["Retail"],
        confidence="Medium",
    )
    db.add_all([profile, assessment])
    db.commit()

    lead_score = ScoringService().upsert_score(db, assessment)
    db.commit()

    assert lead_score.target_industries == ["Retail"]
    assert lead_score.assessment_id == assessment.id
