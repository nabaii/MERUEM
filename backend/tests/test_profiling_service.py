from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.models.cluster import Cluster
from app.db.models.post import Post
from app.db.models.profile_interest import ProfileInterest
from app.db.models.social_profile import SocialProfile
from app.services.profiling_service import ProfilingService


def test_build_prompt_for_profile_includes_context(db):
    cluster = Cluster(label="Fintech Builders", member_count=24, top_interests={"fintech": 10})
    db.add(cluster)
    db.flush()

    profile = SocialProfile(
        id=uuid.uuid4(),
        platform="twitter",
        platform_user_id="tw_ada",
        username="adadev",
        display_name="Ada Dev",
        bio="Building fintech tools for SMEs in Lagos",
        location_raw="Lagos",
        location_inferred="Lagos, Nigeria",
        follower_count=12000,
        following_count=800,
        cluster_id=cluster.id,
    )
    db.add(profile)
    db.flush()

    db.add_all(
        [
            Post(
                id=uuid.uuid4(),
                profile_id=profile.id,
                platform_post_id="p1",
                content="Helping merchants get paid faster with better checkout flows.",
                entities={"hashtags": ["fintech", "lagos"], "mentions": ["@paystack"], "urls": []},
                sentiment_score=0.55,
                posted_at=datetime.now(timezone.utc),
            ),
            Post(
                id=uuid.uuid4(),
                profile_id=profile.id,
                platform_post_id="p2",
                content="SME growth in Nigeria needs better rails and fewer failed transfers.",
                entities={"hashtags": ["payments"], "mentions": [], "urls": ["https://example.com"]},
                sentiment_score=0.35,
                posted_at=datetime.now(timezone.utc),
            ),
            ProfileInterest(
                id=uuid.uuid4(),
                profile_id=profile.id,
                topic="fintech",
                confidence=0.98,
            ),
        ]
    )
    db.commit()

    prompt = ProfilingService().build_prompt_for_profile(db, profile.id)
    assert "Platform: twitter" in prompt
    assert "Handle: adadev" in prompt
    assert "Fintech Builders" in prompt
    assert "Helping merchants get paid faster" in prompt
    assert "fintech" in prompt


def test_parse_assessment_text_handles_markdown_json():
    raw = """```json
    {
      "persona": "Hustling Professional",
      "primary_interests": ["fintech", "payments"],
      "secondary_interests": ["productivity"],
      "sentiment_tone": "Optimistic",
      "purchase_intent_score": 8,
      "influence_tier": "Micro",
      "engagement_style": "Creator",
      "psychographic_driver": "Achievement",
      "recommended_channel": "LinkedIn",
      "recommended_message_angle": "Lead with growth outcomes.",
      "industry_fit": ["Fintech", "SaaS"],
      "confidence": "High"
    }
    ```"""

    payload = ProfilingService().parse_assessment_text(raw)
    assert payload.persona == "Hustling Professional"
    assert payload.purchase_intent_score == 8
    assert payload.industry_fit == ["Fintech", "SaaS"]


def test_assess_profile_marks_insufficient_data_without_api_key(db):
    profile = SocialProfile(
        id=uuid.uuid4(),
        platform="twitter",
        platform_user_id="tw_empty",
        username="emptyprofile",
        display_name="Empty Profile",
        bio="",
        follower_count=0,
        following_count=0,
    )
    db.add(profile)
    db.commit()

    assessment = ProfilingService().assess_profile(db, profile.id)
    assert assessment.social_profile_id == profile.id
    assert assessment.confidence == "Insufficient Data"
    assert "Skipped profiling" in (assessment.raw_llm_response or "")
