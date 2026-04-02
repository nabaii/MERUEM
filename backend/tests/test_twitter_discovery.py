from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.db.models.discovery_job import DiscoveryJob, DiscoveryStatus
from app.db.models.post import Post
from app.services.twitter_user_profiler import TwitterUserProfiler
from app.schemas.discovery import DiscoveredUser


def test_twitter_user_profiler_enriches_users_without_llm(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    profiler = TwitterUserProfiler()

    user = DiscoveredUser(
        platform_user_id="tw_ride",
        user_id="tw_ride",
        username="ridewithken",
        display_name="Ken Ride",
        bio="Uber driver in Lagos. Email: ken@example.com",
        location_raw="Lagos, Nigeria",
        follower_count=420,
        following_count=180,
        tweet_count=1800,
        location_match=True,
        date_joined_twitter="2021-05-20T10:00:00+00:00",
    )

    recent_tweets = [
        {
            "id": "t1",
            "text": "Fuel price is wild again. Need a fuel-saving car for daily Uber runs.",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "public_metrics": {"like_count": 8, "retweet_count": 2, "reply_count": 5},
            "referenced_tweets": [{"type": "replied_to", "id": "root-1"}],
        },
        {
            "id": "t2",
            "text": "Are hybrid cars worth it in Lagos traffic and long commutes?",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "public_metrics": {"like_count": 5, "retweet_count": 1, "reply_count": 4},
            "referenced_tweets": [],
        },
    ]

    enriched = profiler.enrich_users(
        [user],
        keywords=["fuel price", "hybrid car"],
        target_location="Nigeria",
        fetch_recent_tweets=lambda _user_id, _limit: recent_tweets,
    )[0]

    assert enriched.user_type == "Ride-Hailing Driver"
    assert enriched.public_contact_info.emails == ["ken@example.com"]
    assert len(enriched.last_10_tweets) == 2
    assert enriched.topic_relevance_score > 50
    assert enriched.conversion_likelihood_score > 40
    assert enriched.high_value_score > 50
    assert enriched.recommended_angle is not None


def test_discovery_search_supports_dummy_mode(client, db, monkeypatch):
    monkeypatch.setattr(settings, "twitter_bearer_token", "")

    response = client.post(
        "/api/v1/discovery/search",
        json={
            "seed_keywords": ["fuel price pain"],
            "expanded_keywords": ["hybrid car"],
            "location": "Nigeria",
            "date_from": "2026-03-01",
            "date_to": "2026-03-31",
            "max_results": 60,
            "dummy_mode": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dummy_mode"] is True
    assert payload["profiled_users_count"] >= 3
    assert payload["high_value_users_found"] >= 1
    assert payload["users"][0]["last_10_tweets"]
    assert payload["users"][0]["public_contact_info"]["social_handles"]

    job = db.query(DiscoveryJob).filter_by(id=uuid.UUID(payload["job_id"])).first()
    assert job is not None
    assert job.results_data["dummy_mode"] is True
    assert len(job.results_data["users"]) == payload["total_users_found"]


def test_save_discovered_users_persists_recent_and_matching_tweets(client, db):
    job_id = uuid.uuid4()
    db.add(
        DiscoveryJob(
            id=job_id,
            platform="twitter",
            seed_keywords=["fuel price"],
            expanded_keywords=["hybrid car"],
            location="Nigeria",
            status=DiscoveryStatus.completed,
            results_count=1,
            tweets_scanned=12,
            location_matched=1,
            results_data={
                "users": [
                    {
                        "platform_user_id": "tw_profiled",
                        "user_id": "tw_profiled",
                        "username": "profileduser",
                        "display_name": "Profiled User",
                        "bio": "Driver and auto enthusiast",
                        "location_raw": "Lagos",
                        "profile_image_url": None,
                        "follower_count": 900,
                        "following_count": 210,
                        "tweet_count": 3400,
                        "location_match": True,
                        "relevance_score": 81,
                        "matching_tweets": [
                            {
                                "tweet_id": "tweet-match",
                                "content": "Hybrid cars could reduce my fuel spend.",
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "likes": 4,
                                "retweets": 1,
                                "replies": 2,
                                "post_type": "tweet",
                            }
                        ],
                        "last_10_tweets": [
                            {
                                "tweet_id": "tweet-recent",
                                "content": "Replying because fuel costs are painful for drivers.",
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "likes": 6,
                                "retweets": 0,
                                "replies": 3,
                                "post_type": "reply",
                            },
                            {
                                "tweet_id": "tweet-match",
                                "content": "Hybrid cars could reduce my fuel spend.",
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "likes": 4,
                                "retweets": 1,
                                "replies": 2,
                                "post_type": "tweet",
                            },
                        ],
                        "date_joined_twitter": "2020-01-01T00:00:00+00:00",
                        "user_type": "Ride-Hailing Driver",
                        "public_contact_info": {
                            "emails": [],
                            "phone_numbers": [],
                            "social_handles": [],
                            "urls": [],
                        },
                        "engagement_frequency_score": 70,
                        "topic_relevance_score": 78,
                        "conversation_influence_score": 60,
                        "conversion_likelihood_score": 72,
                        "high_value_score": 71,
                        "high_value_band": "High",
                        "hybrid_signals": ["Mentions transport pain points"],
                        "actionable_insights": ["Good candidate for hybrid fuel-savings messaging."],
                        "recommended_angle": "Lead with daily fuel savings.",
                        "manual_followers_note": "Follower list should be gathered manually.",
                    }
                ],
                "profiled_users_count": 1,
                "high_value_users_found": 1,
            },
        )
    )
    db.commit()

    response = client.post(
        "/api/v1/discovery/save-users",
        json={"discovery_job_id": str(job_id), "user_indices": [0]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["saved_count"] == 1

    posts = db.query(Post).filter(Post.profile_id == uuid.UUID(payload["profile_ids"][0])).all()
    assert len(posts) == 2
    assert {post.platform_post_id for post in posts} == {"tweet-recent", "tweet-match"}
    assert any(post.post_type == "reply" for post in posts)


def test_manual_enrichment_shared_followings_and_export(client, db):
    job_id = uuid.uuid4()
    db.add(
        DiscoveryJob(
            id=job_id,
            platform="twitter",
            seed_keywords=["fuel price"],
            expanded_keywords=["hybrid car"],
            location="Nigeria",
            status=DiscoveryStatus.completed,
            results_count=3,
            tweets_scanned=20,
            location_matched=2,
            results_data={
                "users": [
                    {
                        "platform_user_id": "u1",
                        "user_id": "u1",
                        "username": "targetone",
                        "display_name": "Target One",
                        "bio": "Commuter in Lagos",
                        "location_raw": "Lagos",
                        "profile_image_url": None,
                        "follower_count": 800,
                        "following_count": 250,
                        "tweet_count": 1200,
                        "location_match": True,
                        "relevance_score": 75,
                        "matching_tweets": [],
                        "last_10_tweets": [],
                        "date_joined_twitter": "2021-01-01T00:00:00+00:00",
                        "user_type": "Commuter",
                        "public_contact_info": {"emails": [], "phone_numbers": [], "social_handles": [], "urls": []},
                        "engagement_frequency_score": 60,
                        "topic_relevance_score": 70,
                        "conversation_influence_score": 50,
                        "conversion_likelihood_score": 65,
                        "high_value_score": 62,
                        "high_value_band": "Medium",
                        "hybrid_signals": [],
                        "actionable_insights": [],
                        "recommended_angle": "Lead with fuel savings.",
                        "manual_followers_note": "Follower list should be gathered manually.",
                    },
                    {
                        "platform_user_id": "u2",
                        "user_id": "u2",
                        "username": "targettwo",
                        "display_name": "Target Two",
                        "bio": "Ride-hailing driver",
                        "location_raw": "Abuja",
                        "profile_image_url": None,
                        "follower_count": 1200,
                        "following_count": 300,
                        "tweet_count": 1500,
                        "location_match": True,
                        "relevance_score": 82,
                        "matching_tweets": [],
                        "last_10_tweets": [],
                        "date_joined_twitter": "2020-01-01T00:00:00+00:00",
                        "user_type": "Ride-Hailing Driver",
                        "public_contact_info": {"emails": [], "phone_numbers": [], "social_handles": [], "urls": []},
                        "engagement_frequency_score": 68,
                        "topic_relevance_score": 77,
                        "conversation_influence_score": 60,
                        "conversion_likelihood_score": 72,
                        "high_value_score": 70,
                        "high_value_band": "High",
                        "hybrid_signals": [],
                        "actionable_insights": [],
                        "recommended_angle": "Lead with cost reduction.",
                        "manual_followers_note": "Follower list should be gathered manually.",
                    },
                    {
                        "platform_user_id": "u3",
                        "user_id": "u3",
                        "username": "microauto",
                        "display_name": "Micro Auto",
                        "bio": "Automotive creator",
                        "location_raw": "Lagos",
                        "profile_image_url": None,
                        "follower_count": 15000,
                        "following_count": 400,
                        "tweet_count": 5000,
                        "location_match": True,
                        "relevance_score": 90,
                        "matching_tweets": [],
                        "last_10_tweets": [],
                        "date_joined_twitter": "2019-01-01T00:00:00+00:00",
                        "user_type": "Automotive Creator",
                        "public_contact_info": {"emails": [], "phone_numbers": [], "social_handles": [], "urls": []},
                        "engagement_frequency_score": 75,
                        "topic_relevance_score": 88,
                        "conversation_influence_score": 78,
                        "conversion_likelihood_score": 74,
                        "high_value_score": 79,
                        "high_value_band": "High",
                        "hybrid_signals": [],
                        "actionable_insights": [],
                        "recommended_angle": "Lead with reliability.",
                        "manual_followers_note": "Follower list should be gathered manually.",
                    },
                ],
                "profiled_users_count": 3,
                "high_value_users_found": 2,
                "selected_micro_influencers": [],
            },
        )
    )
    db.commit()

    response = client.patch(
        f"/api/v1/discovery/{job_id}/users/0/manual-enrichment",
        json={
            "followers_list": ["@driver_one", "@driver_two"],
            "following_list": ["@microauto", "@fueltips"],
            "notes": "Shared transport accounts worth tracking.",
        },
    )
    assert response.status_code == 200
    assert response.json()["manual_followers_list"] == ["driver_one", "driver_two"]
    assert response.json()["manual_following_list"] == ["microauto", "fueltips"]

    response = client.patch(
        f"/api/v1/discovery/{job_id}/users/1/manual-enrichment",
        json={
            "followers_list": ["@rider_one"],
            "following_list": ["@microauto", "@fueltips", "@hybridnaija"],
            "notes": "Also follows transport educators.",
        },
    )
    assert response.status_code == 200

    response = client.post(
        f"/api/v1/discovery/{job_id}/shared-followings/analyze",
        json={"user_indices": [0, 1], "min_overlap": 2, "max_candidates": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] >= 2
    assert payload["candidates"][0]["username"] == "microauto"
    assert payload["candidates"][0]["overlap_count"] == 2

    response = client.patch(
        f"/api/v1/discovery/{job_id}/shared-followings/selection",
        json={"usernames": ["microauto"]},
    )
    assert response.status_code == 200
    assert any(item["selected"] for item in response.json()["candidates"])

    response = client.get(f"/api/v1/discovery/{job_id}/export/csv")
    assert response.status_code == 200
    csv_text = response.text
    assert "manual_followers_list" in csv_text
    assert "driver_one | driver_two" in csv_text
    assert "selected_as_micro_influencer" in csv_text
    assert "true" in csv_text.lower()
