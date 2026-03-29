"""
Named entity extraction for Phase 2.

Uses spaCy en_core_web_sm for standard NER plus hand-crafted rules for
Nigerian brands, locations, and common slang terms.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Nigerian knowledge base
# ---------------------------------------------------------------------------

NIGERIAN_BRANDS: list[str] = [
    # Banks
    "GTBank", "GT Bank", "Guaranty Trust", "Zenith Bank", "Access Bank",
    "First Bank", "UBA", "United Bank for Africa", "Fidelity Bank",
    "Stanbic IBTC", "Ecobank", "FCMB", "Heritage Bank", "Wema Bank",
    "Polaris Bank", "Unity Bank", "Jaiz Bank", "Sterling Bank",
    # Fintechs
    "Flutterwave", "Paystack", "Interswitch", "Kuda", "PiggyVest",
    "Cowrywise", "OPay", "PalmPay", "VBank", "FairMoney", "Carbon",
    "Renmoney", "Paga", "Moniepoint", "TeamApt",
    # Telecoms
    "MTN Nigeria", "MTN", "Airtel Nigeria", "Airtel", "Glo", "Globacom",
    "9mobile", "Etisalat",
    # FMCG / conglomerates
    "Dangote", "Nestle Nigeria", "Unilever Nigeria", "Nigerian Breweries",
    "Guinness Nigeria", "Cadbury Nigeria", "PZ Cussons", "Innoson",
    # E-commerce / logistics
    "Jumia", "Konga", "Jiji", "Cars45", "Autochek", "MAX",
    # Media / entertainment
    "Channels TV", "AIT", "NTA", "TVC", "Arise TV", "Silverbird",
    "Punch", "Vanguard", "The Nation", "Guardian Nigeria", "Premium Times",
    "Nollywood", "Afrobeats",
]

NIGERIAN_CITIES: list[str] = [
    "Lagos", "Abuja", "Port Harcourt", "Kano", "Ibadan", "Benin City",
    "Calabar", "Enugu", "Kaduna", "Jos", "Owerri", "Uyo", "Warri",
    "Asaba", "Abeokuta", "Akure", "Ilorin", "Bauchi", "Maiduguri",
    "Sokoto", "Zaria", "Aba", "Onitsha", "Awka", "Yola", "Makurdi",
    "Lafia", "Dutse", "Birnin Kebbi", "Gusau", "Damaturu", "Jalingo",
    "Lokoja", "Minna", "Gombe", "Ikeja", "Victoria Island", "Lekki",
    "Surulere", "Yaba", "Ikoyi", "Ajah", "Sangotedo",
]

NIGERIAN_STATES: list[str] = [
    "Lagos", "Abuja", "FCT", "Rivers", "Kano", "Oyo", "Edo",
    "Cross River", "Enugu", "Kaduna", "Plateau", "Imo", "Akwa Ibom",
    "Delta", "Anambra", "Kwara", "Ogun", "Ondo", "Kogi", "Benue",
    "Niger", "Kebbi", "Sokoto", "Zamfara", "Yobe", "Borno", "Adamawa",
    "Taraba", "Gombe", "Bauchi", "Jigawa", "Katsina", "Nasarawa",
    "Ebonyi", "Ekiti", "Osun", "Abia", "Bayelsa",
]

# Pre-compiled brand patterns (case-insensitive)
_BRAND_PATTERNS = [(b, re.compile(r"\b" + re.escape(b) + r"\b", re.IGNORECASE)) for b in NIGERIAN_BRANDS]
_CITY_PATTERNS = [(c, re.compile(r"\b" + re.escape(c) + r"\b", re.IGNORECASE)) for c in NIGERIAN_CITIES]
_STATE_PATTERNS = [(s, re.compile(r"\b" + re.escape(s) + r"\b", re.IGNORECASE)) for s in NIGERIAN_STATES]

_HASHTAG_RE = re.compile(r"#(\w+)")
_MENTION_RE = re.compile(r"@(\w+)")


# ---------------------------------------------------------------------------
# spaCy loader (lazy singleton — loaded once per process)
# ---------------------------------------------------------------------------

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm", disable=["parser", "tagger", "lemmatizer"])
            log.info("spaCy en_core_web_sm loaded")
        except Exception as exc:
            log.warning("spaCy model unavailable (%s) — NER will be rule-based only", exc)
            _nlp = False  # sentinel: tried and failed
    return _nlp if _nlp is not False else None


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_entities(raw_text: str) -> dict[str, Any]:
    """
    Extract structured entities from a raw (uncleaned) post.

    Returns a dict with keys:
      hashtags, mentions, nigerian_brands, nigerian_locations,
      spacy_entities (list of {text, label} dicts)
    """
    if not raw_text:
        return _empty_entities()

    result: dict[str, Any] = {
        "hashtags": _HASHTAG_RE.findall(raw_text),
        "mentions": _MENTION_RE.findall(raw_text),
        "nigerian_brands": [],
        "nigerian_locations": [],
        "spacy_entities": [],
    }

    # Rule-based Nigerian brand detection
    for brand, pat in _BRAND_PATTERNS:
        if pat.search(raw_text):
            result["nigerian_brands"].append(brand)

    # Rule-based Nigerian location detection
    for loc, pat in _CITY_PATTERNS + _STATE_PATTERNS:
        if pat.search(raw_text):
            if loc not in result["nigerian_locations"]:
                result["nigerian_locations"].append(loc)

    # spaCy NER (if available)
    nlp = _get_nlp()
    if nlp:
        doc = nlp(raw_text[:1000])  # cap at 1000 chars for speed
        for ent in doc.ents:
            result["spacy_entities"].append({"text": ent.text, "label": ent.label_})
            if ent.label_ in ("GPE", "LOC") and ent.text not in result["nigerian_locations"]:
                result["nigerian_locations"].append(ent.text)

    return result


def _empty_entities() -> dict[str, Any]:
    return {
        "hashtags": [],
        "mentions": [],
        "nigerian_brands": [],
        "nigerian_locations": [],
        "spacy_entities": [],
    }
