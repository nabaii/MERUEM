"""
Text cleaning utilities for Phase 2 processing pipeline.

Handles:
- Unicode normalisation (NFKC via ftfy)
- URL and @mention stripping
- Retweet / repost detection and deduplication
- Language detection (English, Pidgin, Yoruba, Hausa, and others)
"""

import re
import unicodedata

import ftfy
from langdetect import DetectorFactory, LangDetectException, detect

# Make langdetect deterministic
DetectorFactory.seed = 42

# Pidgin Nigerian markers — used when langdetect returns "en" for clearly Pidgin text
_PIDGIN_MARKERS = frozenset(
    [
        "oya", "wahala", "dey", "nah", "sha", "abeg", "abi", "ehn",
        "wetin", "shey", "una", "jare", "omo", "kpele", "ehen", "bros",
        "sabi", "chop", "ginger", "mugu", "yahoo", "wack", "naija",
        "wey", "comot", "don", "sef", "oya na", "no be", "e don",
    ]
)

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#\w+")
_WHITESPACE_RE = re.compile(r"\s+")
_RT_RE = re.compile(r"^RT\s+@\w+:\s*", re.IGNORECASE)


def fix_encoding(text: str) -> str:
    """Fix mojibake and normalise to NFKC Unicode."""
    return unicodedata.normalize("NFKC", ftfy.fix_text(text))


def strip_urls(text: str) -> str:
    return _URL_RE.sub("", text)


def strip_mentions(text: str) -> str:
    return _MENTION_RE.sub("", text)


def clean_text(text: str) -> str:
    """
    Full cleaning pass: fix encoding → strip URLs → strip mentions → collapse whitespace.
    Hashtags are kept (useful for entity extraction and embedding).
    """
    text = fix_encoding(text)
    text = strip_urls(text)
    text = strip_mentions(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def is_retweet(raw_text: str) -> bool:
    """Return True if the raw post text is a native retweet (starts with 'RT @')."""
    return bool(_RT_RE.match(raw_text or ""))


def extract_hashtags(raw_text: str) -> list[str]:
    """Return all hashtags from raw (uncleaned) text, lowercase."""
    return [h.lower() for h in _HASHTAG_RE.findall(raw_text or "")]


def detect_language(text: str) -> str:
    """
    Detect language code.  Returns ISO 639-1 codes plus 'pcm' for Nigerian Pidgin.
    Falls back to 'unknown' if text is too short or ambiguous.
    """
    if not text or len(text.split()) < 3:
        return "unknown"

    try:
        lang = detect(text)
    except LangDetectException:
        return "unknown"

    # Refine English detections: check for Pidgin markers
    if lang == "en":
        text_lower = text.lower()
        pidgin_hits = sum(1 for m in _PIDGIN_MARKERS if m in text_lower)
        if pidgin_hits >= 2:
            return "pcm"  # Nigerian Pidgin Creole

    return lang
