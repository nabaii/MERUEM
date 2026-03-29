"""
Cross-platform identity resolution — Phase 3.

Matches SocialProfile rows from different platforms that likely belong to the
same real person, using a multi-signal scoring model:

  Signal                      Max contribution
  ─────────────────────────── ────────────────
  Display-name similarity     0.50
  Username similarity         0.30
  Shared bio URL              0.40
  Bio text similarity         0.20
  ─────────────────────────── ────────────────
  Combined (capped at 1.0)    1.00

Confidence thresholds
─────────────────────
  ≥ AUTO_CONFIRM_THRESHOLD  → ProfileLink status = confirmed, UnifiedUser created
  ≥ REVIEW_THRESHOLD        → ProfileLink status = pending  (manual review queue)
  <  REVIEW_THRESHOLD        → ignored

All string comparisons use rapidfuzz so they handle minor typos and
formatting differences ("john doe" vs "John Doe" vs "johndoe").
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

# ── thresholds ────────────────────────────────────────────────────────────────
AUTO_CONFIRM_THRESHOLD = 0.85  # auto-create UnifiedUser
REVIEW_THRESHOLD = 0.50        # add to manual review queue

# ── weights ───────────────────────────────────────────────────────────────────
W_DISPLAY_NAME = 0.50
W_USERNAME = 0.30
W_BIO_URL = 0.40
W_BIO_TEXT = 0.20

# ── helpers ───────────────────────────────────────────────────────────────────
_URL_RE = re.compile(
    r"https?://(?:www\.)?([a-z0-9\-]+\.[a-z]{2,}(?:/[^\s]*)?)",
    re.IGNORECASE,
)
_HANDLE_RE = re.compile(r"[^a-z0-9]")


def _normalise_name(s: str) -> str:
    return s.lower().strip()


def _normalise_handle(s: str) -> str:
    return _HANDLE_RE.sub("", s.lower())


def _extract_urls(bio: str | None) -> set[str]:
    if not bio:
        return set()
    return {m.group(1).lower() for m in _URL_RE.finditer(bio)}


def _name_sim(a: str, b: str) -> float:
    """Token-sort ratio — handles word order differences and extra tokens."""
    return fuzz.token_sort_ratio(_normalise_name(a), _normalise_name(b)) / 100.0


def _handle_sim(a: str, b: str) -> float:
    """Partial ratio on stripped handles — handles @prefix differences."""
    return fuzz.partial_ratio(_normalise_handle(a), _normalise_handle(b)) / 100.0


def _bio_sim(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a.lower(), b.lower()) / 100.0


# ── public API ────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    source_profile_id: str
    target_profile_id: str
    confidence: float
    match_method: str       # comma-joined list of contributing signals
    status: str             # "confirmed" | "pending"


def score_pair(
    *,
    source_id: str,
    source_display_name: str | None,
    source_username: str | None,
    source_bio: str | None,
    target_id: str,
    target_display_name: str | None,
    target_username: str | None,
    target_bio: str | None,
) -> MatchResult | None:
    """
    Score one profile pair.  Returns None when confidence < REVIEW_THRESHOLD.
    """
    signals: list[str] = []
    score = 0.0

    # ── display name ──────────────────────────────────────────────────────────
    if source_display_name and target_display_name:
        ns = _name_sim(source_display_name, target_display_name)
        if ns >= 0.80:
            contribution = W_DISPLAY_NAME * ns
            score += contribution
            signals.append(f"name({ns:.2f})")

    # ── username ──────────────────────────────────────────────────────────────
    if source_username and target_username:
        hs = _handle_sim(source_username, target_username)
        if hs >= 0.75:
            contribution = W_USERNAME * hs
            score += contribution
            signals.append(f"username({hs:.2f})")

    # ── shared bio URL ────────────────────────────────────────────────────────
    src_urls = _extract_urls(source_bio)
    tgt_urls = _extract_urls(target_bio)
    shared_urls = src_urls & tgt_urls
    if shared_urls:
        score += W_BIO_URL
        signals.append(f"bio_url({len(shared_urls)})")

    # ── bio text similarity ───────────────────────────────────────────────────
    bs = _bio_sim(source_bio, target_bio)
    if bs >= 0.70:
        contribution = W_BIO_TEXT * bs
        score += contribution
        signals.append(f"bio_text({bs:.2f})")

    confidence = min(round(score, 4), 1.0)

    if confidence < REVIEW_THRESHOLD:
        return None

    status = "confirmed" if confidence >= AUTO_CONFIRM_THRESHOLD else "pending"
    return MatchResult(
        source_profile_id=source_id,
        target_profile_id=target_id,
        confidence=confidence,
        match_method=",".join(signals),
        status=status,
    )
