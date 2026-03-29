"""
Tests for sentiment module.
The HuggingFace model is mocked so these run without GPU or a model download.
"""

from unittest.mock import patch

from app.processing.sentiment import aggregate_profile_sentiment, score_sentiment


def _make_pipe(label: str, score: float):
    """Return a mock pipeline callable."""
    def _pipe(text, **kwargs):
        return [{"label": label, "score": score}]
    return _pipe


def test_positive_sentiment():
    with patch("app.processing.sentiment._get_pipeline", return_value=_make_pipe("positive", 0.95)):
        result = score_sentiment("This is absolutely amazing and wonderful!")
    assert result == 0.95


def test_negative_sentiment():
    with patch("app.processing.sentiment._get_pipeline", return_value=_make_pipe("negative", 0.80)):
        result = score_sentiment("This is terrible and very disappointing")
    assert result == -0.80


def test_neutral_sentiment():
    with patch("app.processing.sentiment._get_pipeline", return_value=_make_pipe("neutral", 0.70)):
        result = score_sentiment("The weather is okay today")
    assert result == 0.0


def test_empty_text_returns_zero():
    result = score_sentiment("")
    assert result == 0.0


def test_very_short_text_returns_zero():
    result = score_sentiment("Ok")
    assert result == 0.0


def test_model_unavailable_returns_zero():
    with patch("app.processing.sentiment._get_pipeline", return_value=None):
        result = score_sentiment("Great product from Paystack!")
    assert result == 0.0


def test_aggregate_profile_sentiment():
    scores = [0.9, -0.5, 0.0, 0.8, -0.3]
    agg = aggregate_profile_sentiment(scores)
    # Only non-zero: [0.9, -0.5, 0.8, -0.3] → mean = 0.225
    assert abs(agg - 0.225) < 0.01


def test_aggregate_all_zero():
    assert aggregate_profile_sentiment([0.0, 0.0]) == 0.0


def test_aggregate_empty():
    assert aggregate_profile_sentiment([]) == 0.0
