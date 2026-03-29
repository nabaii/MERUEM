"""Tests for the keyword/hashtag topic classifier."""

import pytest

from app.intelligence.topic_classifier import CONFIDENCE_THRESHOLD, classify_profile


def test_empty_profile_returns_empty():
    result = classify_profile(bio=None, post_texts=[], post_hashtags=[])
    assert result == []


def test_tech_bio():
    result = classify_profile(
        bio="Software developer. Building AI startups.",
        post_texts=[],
        post_hashtags=[],
    )
    topics = {r["topic"] for r in result}
    assert "tech" in topics


def test_music_hashtags():
    result = classify_profile(
        bio=None,
        post_texts=["New track dropping Friday"],
        post_hashtags=[["#afrobeats", "#newmusic", "#amapiano"]],
    )
    topics = {r["topic"] for r in result}
    assert "music" in topics


def test_multi_label():
    """A fashion tech influencer should get both topics."""
    result = classify_profile(
        bio="Fashion lover and software developer",
        post_texts=["Check out my new outfit", "Just pushed code"],
        post_hashtags=[["#ootd", "#fashion"], ["#coding", "#developer"]],
    )
    topics = {r["topic"] for r in result}
    assert "fashion" in topics
    assert "tech" in topics


def test_confidence_threshold_respected():
    """No result should be below the configured threshold."""
    result = classify_profile(
        bio="I love food and cooking Nigerian meals like jollof rice",
        post_texts=["suya is amazing", "trying new recipes"],
        post_hashtags=[["#naijafood"], ["#recipe"]],
    )
    for item in result:
        assert item["confidence"] >= CONFIDENCE_THRESHOLD


def test_scores_sorted_descending():
    result = classify_profile(
        bio="Finance investor and crypto trader",
        post_texts=["forex analysis", "bitcoin portfolio update", "stocks are up"],
        post_hashtags=[["#fintech", "#investment"], ["#crypto"], ["#stocks"]],
    )
    if len(result) > 1:
        confidences = [r["confidence"] for r in result]
        assert confidences == sorted(confidences, reverse=True)


def test_top_topic_always_confidence_one():
    """The highest-scoring topic is always normalised to 1.0."""
    result = classify_profile(
        bio="Sports journalist covering Super Eagles matches",
        post_texts=["AFCON update: Nigeria win!"],
        post_hashtags=[["#supereagles", "#football", "#sports"]],
    )
    assert result, "Expected at least one topic"
    assert result[0]["confidence"] == 1.0


def test_nigerian_specific_terms():
    """Nollywood should map to entertainment; afrobeats to music."""
    result = classify_profile(
        bio="Nollywood actress and afrobeats fan",
        post_texts=["Latest nollywood film out now"],
        post_hashtags=[["#nollywood", "#afrobeats"]],
    )
    topics = {r["topic"] for r in result}
    assert "entertainment" in topics
    assert "music" in topics
