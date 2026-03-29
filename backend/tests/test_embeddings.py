"""
Tests for embeddings module.
SentenceTransformer is mocked so tests run without downloading the model.
"""

from unittest.mock import MagicMock, patch

import numpy as np

from app.processing.embeddings import build_profile_text, embed_profile


def test_build_profile_text_full():
    text = build_profile_text(
        bio="Lagos-based fintech founder",
        cleaned_tweets=["Paystack is great", "Building the future"],
        hashtags=["#fintech", "#lagos"],
    )
    assert "fintech founder" in text
    assert "Paystack" in text
    assert "#fintech" in text


def test_build_profile_text_empty_bio():
    text = build_profile_text(bio=None, cleaned_tweets=["Hello Lagos"], hashtags=[])
    assert "Hello Lagos" in text


def test_build_profile_text_empty():
    text = build_profile_text(bio=None, cleaned_tweets=[], hashtags=[])
    assert text == ""


def test_embed_profile_returns_384_dims():
    fake_vector = np.ones(384, dtype=np.float32)

    mock_model = MagicMock()
    mock_model.encode.return_value = fake_vector

    with patch("app.processing.embeddings._get_model", return_value=mock_model):
        result = embed_profile(
            bio="Entrepreneur in Lagos",
            cleaned_tweets=["Building the next big thing"],
            hashtags=["#naija"],
        )

    assert result is not None
    assert len(result) == 384
    assert all(isinstance(v, float) for v in result)


def test_embed_profile_empty_text_returns_none():
    with patch("app.processing.embeddings._get_model", return_value=MagicMock()):
        result = embed_profile(bio=None, cleaned_tweets=[], hashtags=[])
    assert result is None


def test_embed_profile_model_unavailable():
    with patch("app.processing.embeddings._get_model", return_value=None):
        result = embed_profile(
            bio="Some bio",
            cleaned_tweets=["tweet"],
            hashtags=[],
        )
    assert result is None


def test_hashtag_deduplication():
    text = build_profile_text(
        bio=None,
        cleaned_tweets=[],
        hashtags=["#lagos", "#lagos", "#fintech", "#fintech"],
    )
    # Each hashtag should appear only once
    assert text.count("#lagos") == 1
    assert text.count("#fintech") == 1
