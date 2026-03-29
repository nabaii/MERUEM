"""
Sentence-transformer embedding generation for Phase 2.

Model: all-MiniLM-L6-v2  →  384-dimensional L2-normalised vectors
Stored in social_profiles.embedding (pgvector Vector(384)).

The model is loaded once per worker process (lazy singleton).
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(_MODEL_NAME)
            log.info("Embedding model loaded: %s", _MODEL_NAME)
        except Exception as exc:
            log.warning("Embedding model unavailable (%s) — embeddings will be skipped", exc)
            _model = False
    return _model if _model is not False else None


def build_profile_text(
    bio: str | None,
    cleaned_tweets: list[str],
    hashtags: list[str],
) -> str:
    """
    Concatenate bio + recent tweet text + hashtags into a single string for embedding.

    We cap tweets at 30 and hashtags at 60 to stay within the model's context window
    while still capturing the profile's vocabulary.
    """
    parts: list[str] = []

    if bio:
        parts.append(bio)

    if cleaned_tweets:
        parts.append(" ".join(cleaned_tweets[:30]))

    if hashtags:
        # De-duplicate while preserving order
        seen: set[str] = set()
        unique = [h for h in hashtags if not (h in seen or seen.add(h))]  # type: ignore[func-returns-value]
        parts.append(" ".join(unique[:60]))

    return " ".join(parts).strip()


def embed_profile(
    bio: str | None,
    cleaned_tweets: list[str],
    hashtags: list[str],
) -> list[float] | None:
    """
    Return a 384-dim L2-normalised embedding vector, or None if the model is unavailable.
    """
    model = _get_model()
    if model is None:
        return None

    text = build_profile_text(bio, cleaned_tweets, hashtags)
    if not text:
        return None

    try:
        vector: np.ndarray = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
    except Exception as exc:
        log.warning("Embedding failed: %s", exc)
        return None
