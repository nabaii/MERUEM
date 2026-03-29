"""
Multi-label topic classifier — Phase 3a: keyword / hashtag rule engine.

Each profile is scored across 10 topics using weighted keyword matches in:
  - bio (weight 3×)
  - post hashtags (weight 2×)
  - post text content (weight 1×, capped per topic to avoid spam bias)

Scores are normalised to [0, 1] relative to the top-scoring topic, then
filtered by CONFIDENCE_THRESHOLD before being stored in profile_interests.

This module is intentionally swappable: replace `classify_profile()` with a
trained sentence-transformer classifier in a later phase without changing the
Celery task or API.
"""

from __future__ import annotations

import re

# ── topic rules ──────────────────────────────────────────────────────────────

TOPIC_RULES: dict[str, dict] = {
    "fashion": {
        "keywords": {
            "fashion", "style", "ootd", "outfit", "wear", "clothes", "dress",
            "wardrobe", "designer", "trends", "slay", "fit", "lewk", "drip",
            "naijafashion", "afristyle",
        },
        "hashtags": {
            "fashion", "ootd", "style", "naijafashion", "africanfashion",
            "outfit", "fashionista", "menswear", "womenswear", "lagos fashion",
        },
    },
    "tech": {
        "keywords": {
            "tech", "software", "coding", "developer", "ai", "startup",
            "innovation", "app", "digital", "programming", "engineer", "data",
            "cloud", "saas", "fintech", "python", "javascript",
        },
        "hashtags": {
            "tech", "software", "coding", "startup", "ai", "developer",
            "programming", "buildinginsouthasia", "techlagos",
        },
    },
    "food": {
        "keywords": {
            "food", "recipe", "cooking", "restaurant", "eat", "chef",
            "cuisine", "foodie", "delicious", "meal", "suya", "jollof",
            "egusi", "pepper soup", "amala", "pounded yam", "buka",
        },
        "hashtags": {
            "food", "foodie", "recipe", "cooking", "naijafood", "jollofrice",
            "foodporn", "cheflife",
        },
    },
    "music": {
        "keywords": {
            "music", "song", "artist", "album", "concert", "afrobeats",
            "playlist", "singer", "dj", "beats", "afropop", "highlife",
            "amapiano", "dancehall", "producer", "track",
        },
        "hashtags": {
            "music", "afrobeats", "afropop", "newmusic", "naijamusicscene",
            "amapiano", "hiphop", "rnb",
        },
    },
    "fitness": {
        "keywords": {
            "fitness", "gym", "workout", "health", "exercise", "training",
            "yoga", "running", "bodybuilding", "diet", "weight", "cardio",
            "physique", "gains", "athlete",
        },
        "hashtags": {
            "fitness", "gym", "workout", "health", "exercise", "training",
            "fitfam", "naijafitness", "bodybuilding",
        },
    },
    "finance": {
        "keywords": {
            "finance", "investment", "crypto", "stocks", "business", "money",
            "wealth", "trading", "fintech", "banking", "savings", "loan",
            "forex", "bitcoin", "portfolio", "investor", "entrepreneur",
        },
        "hashtags": {
            "finance", "investment", "fintech", "crypto", "business",
            "stocks", "forex", "naijainvest", "wealthbuilding",
        },
    },
    "travel": {
        "keywords": {
            "travel", "trip", "vacation", "explore", "adventure", "tourism",
            "hotel", "flight", "wanderlust", "journey", "destination",
            "lagos", "abuja", "nairobi", "accra", "cape town",
        },
        "hashtags": {
            "travel", "explore", "vacation", "wanderlust", "naijatraveller",
            "travelafrica", "visitlagos",
        },
    },
    "entertainment": {
        "keywords": {
            "entertainment", "movie", "film", "series", "nollywood",
            "celebrity", "comedy", "actor", "netflix", "showbiz", "gist",
            "telemundo", "reality tv", "bbnaija", "skit",
        },
        "hashtags": {
            "nollywood", "entertainment", "celebrity", "movies", "comedy",
            "bbnaija", "africanmovies", "skitmaker",
        },
    },
    "politics": {
        "keywords": {
            "politics", "government", "election", "democracy", "policy",
            "president", "minister", "vote", "senate", "governor",
            "tinubu", "obi", "atiku", "inec", "lawmaker", "bill",
        },
        "hashtags": {
            "politics", "election", "nigeria", "government", "democracy",
            "vote", "2027elections",
        },
    },
    "sports": {
        "keywords": {
            "sports", "football", "soccer", "basketball", "supereagles",
            "champions", "match", "league", "athletic", "game", "tournament",
            "laliga", "premierleague", "afcon", "nba", "athletics",
        },
        "hashtags": {
            "sports", "football", "supereagles", "laliga", "premierleague",
            "afcon", "nba", "naijasports",
        },
    },
}

# Bio matches carry the most signal (person deliberately describes themselves)
_BIO_WEIGHT = 3.0
# Explicit hashtag use signals strong intentional interest
_HASHTAG_WEIGHT = 2.0
# General content — up to 5 pts per topic to prevent one spammy post dominating
_CONTENT_WEIGHT = 1.0
_CONTENT_CAP = 5.0

CONFIDENCE_THRESHOLD = 0.15  # drop anything below this after normalisation

_WHITESPACE_RE = re.compile(r"\s+")


def _tokens(text: str) -> set[str]:
    """Lowercase word-token set — fast enough for rule matching."""
    return set(_WHITESPACE_RE.sub(" ", text.lower()).split())


def classify_profile(
    bio: str | None,
    post_texts: list[str],
    post_hashtags: list[list[str]],
) -> list[dict[str, float]]:
    """
    Score a profile across all topics and return a list of
    ``{"topic": str, "confidence": float}`` dicts sorted descending.

    Only topics at or above CONFIDENCE_THRESHOLD are returned.

    Args:
        bio: Profile bio string (may be None).
        post_texts: Cleaned post bodies (list of strings).
        post_hashtags: Per-post hashtag lists (parallel to post_texts).
    """
    bio_tokens = _tokens(bio) if bio else set()
    all_hashtags: set[str] = {
        h.lower().lstrip("#") for tags in post_hashtags for h in tags
    }
    content_blob = " ".join(post_texts).lower()

    raw: dict[str, float] = {}

    for topic, rules in TOPIC_RULES.items():
        score = 0.0
        kw_set: set[str] = rules["keywords"]
        ht_set: set[str] = rules["hashtags"]

        # Bio signal
        for kw in kw_set:
            if kw in bio_tokens:
                score += _BIO_WEIGHT

        # Hashtag signal
        for tag in ht_set:
            if tag in all_hashtags:
                score += _HASHTAG_WEIGHT

        # Content signal (capped)
        content_hits = sum(content_blob.count(kw) for kw in kw_set)
        score += min(content_hits * _CONTENT_WEIGHT, _CONTENT_CAP)

        raw[topic] = score

    # Normalise relative to the highest scorer
    max_score = max(raw.values(), default=0.0)
    if max_score == 0.0:
        return []

    return [
        {"topic": topic, "confidence": round(score / max_score, 4)}
        for topic, score in sorted(raw.items(), key=lambda x: x[1], reverse=True)
        if (score / max_score) >= CONFIDENCE_THRESHOLD
    ]
