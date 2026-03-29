"""
Phase 2 processing pipeline orchestrator.

Runs a single profile through:
  1. Text cleaning + language detection
  2. Entity extraction
  3. Sentiment scoring
  4. Location inference
  5. Embedding generation

Designed to run inside a Celery worker — all imports are local to avoid
loading heavy ML models in the API server process.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.post import Post
from app.db.models.social_profile import SocialProfile

log = logging.getLogger(__name__)


def process_profile(profile: SocialProfile, db: Session) -> dict:
    """
    Run the full NLP pipeline for one profile.

    Returns a summary dict with counts for logging / task result.
    """
    # ------------------------------------------------------------------ #
    # Lazy imports — heavy models only load inside the worker process
    # ------------------------------------------------------------------ #
    from app.processing.embeddings import embed_profile
    from app.processing.entity_extractor import extract_entities
    from app.processing.location_inference import infer_location
    from app.processing.sentiment import aggregate_profile_sentiment, score_sentiment
    from app.processing.text_cleaner import (
        clean_text,
        detect_language,
        extract_hashtags,
        is_retweet,
    )

    # Fetch all unprocessed posts for this profile in one query
    posts: list[Post] = (
        db.query(Post)
        .filter(Post.profile_id == profile.id, Post.is_processed.is_(False))
        .all()
    )

    cleaned_tweets: list[str] = []
    all_hashtags: list[str] = []
    all_sentiment_scores: list[float] = []
    all_entities: list[dict] = []
    processed_count = 0
    skipped_retweets = 0

    for post in posts:
        raw = post.content or ""

        # Skip native retweets
        if is_retweet(raw):
            post.is_processed = True
            skipped_retweets += 1
            db.add(post)
            continue

        # 1. Clean + detect language
        cleaned = clean_text(raw)
        post.language = detect_language(cleaned)

        # 2. Extract entities (on raw text to preserve hashtags + mentions)
        entities = extract_entities(raw)
        post.entities = entities
        all_entities.append(entities)

        # Collect hashtags for embedding
        all_hashtags.extend(extract_hashtags(raw))

        # 3. Sentiment
        sentiment = score_sentiment(cleaned)
        post.sentiment_score = sentiment
        if sentiment != 0.0:
            all_sentiment_scores.append(sentiment)

        # Collect cleaned text for embedding (only readable languages)
        if post.language in ("en", "pcm", "yo", "ha", "ig", "unknown"):
            cleaned_tweets.append(cleaned)

        post.is_processed = True
        db.add(post)
        processed_count += 1

    # Flush post updates before updating the profile
    db.flush()

    # ------------------------------------------------------------------ #
    # Profile-level enrichment
    # ------------------------------------------------------------------ #

    # 4. Location inference
    if not profile.location_inferred:
        profile.location_inferred = infer_location(
            bio=profile.bio,
            location_raw=profile.location_raw,
            tweet_entities_list=all_entities,
        )

    # 5. Embedding generation (only when there's meaningful text)
    embedding = embed_profile(
        bio=profile.bio,
        cleaned_tweets=cleaned_tweets,
        hashtags=all_hashtags,
    )
    if embedding is not None:
        profile.embedding = embedding
        profile.embedding_updated_at = datetime.now(timezone.utc)

    db.add(profile)

    return {
        "profile_id": str(profile.id),
        "posts_processed": processed_count,
        "retweets_skipped": skipped_retweets,
        "embedding_generated": embedding is not None,
        "location_inferred": profile.location_inferred,
        "avg_sentiment": aggregate_profile_sentiment(all_sentiment_scores),
    }
