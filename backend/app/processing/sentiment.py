"""
Multilingual sentiment analysis for Phase 2.

Model: cardiffnlp/twitter-xlm-roberta-base-sentiment
- Trained on Twitter data across 100+ languages (via XLM-RoBERTa)
- Handles English, Nigerian Pidgin, Yoruba-inflected English, etc.
- Labels: negative → −score, neutral → 0, positive → +score

The model is loaded lazily once per worker process and reused across tasks.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
_pipeline = None


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
            _pipeline = hf_pipeline(
                "sentiment-analysis",
                model=_MODEL_NAME,
                tokenizer=_MODEL_NAME,
                max_length=512,
                truncation=True,
                device=-1,  # CPU
            )
            log.info("Sentiment model loaded: %s", _MODEL_NAME)
        except Exception as exc:
            log.warning("Sentiment model unavailable (%s) — returning 0.0 for all posts", exc)
            _pipeline = False
    return _pipeline if _pipeline is not False else None


# Label → sign mapping
_LABEL_SIGN = {
    "positive": 1.0,
    "negative": -1.0,
    "neutral": 0.0,
    # Cardiff model may also return "LABEL_0/1/2" — map those too
    "label_0": -1.0,
    "label_1": 0.0,
    "label_2": 1.0,
}


def score_sentiment(text: str) -> float:
    """
    Return a sentiment score in [−1.0, +1.0].
    0.0 is returned for empty text or when the model is unavailable.
    """
    if not text or len(text.strip()) < 5:
        return 0.0

    pipe = _get_pipeline()
    if pipe is None:
        return 0.0

    try:
        result = pipe(text[:512])[0]
        label = result["label"].lower()
        score = float(result["score"])
        sign = _LABEL_SIGN.get(label, 0.0)
        return round(sign * score, 4)
    except Exception as exc:
        log.debug("Sentiment scoring failed for text snippet: %s", exc)
        return 0.0


def aggregate_profile_sentiment(scores: list[float]) -> float:
    """Mean of non-zero sentiment scores for a profile. Returns 0.0 if no scores."""
    valid = [s for s in scores if s != 0.0]
    if not valid:
        return 0.0
    return round(sum(valid) / len(valid), 4)
