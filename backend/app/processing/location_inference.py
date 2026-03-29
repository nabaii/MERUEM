"""
Location inference for Phase 2.

Strategy (in priority order):
1. Parse profile bio for Nigerian city / state mentions
2. Extract locations from tweet entities (geotag fields + NER)
3. Fallback: raw location string normalisation

The follower-network heuristic (Phase 3 enhancement) is noted but not yet implemented.
"""

from __future__ import annotations

import re

from app.processing.entity_extractor import NIGERIAN_CITIES, NIGERIAN_STATES, _CITY_PATTERNS, _STATE_PATTERNS

# Countries commonly written in Nigerian bios (to be stripped so we get the city)
_COUNTRY_WORDS = re.compile(
    r"\b(nigeria|naija|ng|nigeria🇳🇬|🇳🇬)\b", re.IGNORECASE
)


def infer_location(
    bio: str | None,
    location_raw: str | None,
    tweet_entities_list: list[dict] | None = None,
) -> str | None:
    """
    Return the best-guess Nigerian location string, or None.

    Args:
        bio: Profile biography text.
        location_raw: Raw location string from the platform (often user-entered).
        tweet_entities_list: List of entities dicts from processed posts.
    """
    # 1. Try bio
    if bio:
        loc = _extract_from_text(bio)
        if loc:
            return loc

    # 2. Try raw location field (normalise)
    if location_raw:
        loc = _extract_from_text(location_raw)
        if loc:
            return loc
        # Return the raw value if it looks meaningful and short
        cleaned = _COUNTRY_WORDS.sub("", location_raw).strip(" ,.")
        if cleaned and len(cleaned) <= 60:
            return cleaned.title()

    # 3. Extract from tweet entity locations
    if tweet_entities_list:
        for entities in tweet_entities_list:
            for loc_name in entities.get("nigerian_locations", []):
                if loc_name:
                    return loc_name

    return None


def _extract_from_text(text: str) -> str | None:
    """Return the first Nigerian city or state found in text."""
    # Prefer cities (more specific)
    for city, pat in _CITY_PATTERNS:
        if pat.search(text):
            return city
    for state, pat in _STATE_PATTERNS:
        if pat.search(text):
            return state
    return None


def extract_geotag_from_tweet(tweet_entities: dict) -> str | None:
    """Pull location from spaCy GPE/LOC entities on a single post."""
    for ent in tweet_entities.get("spacy_entities", []):
        if ent.get("label") in ("GPE", "LOC"):
            return ent["text"]
    locs = tweet_entities.get("nigerian_locations", [])
    return locs[0] if locs else None
