"""Tests for the cross-platform identity resolution scorer."""

import pytest

from app.intelligence.identity_resolution import (
    AUTO_CONFIRM_THRESHOLD,
    REVIEW_THRESHOLD,
    score_pair,
    _extract_urls,
    _name_sim,
    _handle_sim,
)


def _pair(**overrides):
    defaults = dict(
        source_id="src-1",
        source_display_name=None,
        source_username=None,
        source_bio=None,
        target_id="tgt-1",
        target_display_name=None,
        target_username=None,
        target_bio=None,
    )
    defaults.update(overrides)
    return defaults


# ── unit helpers ──────────────────────────────────────────────────────────────

def test_name_sim_exact():
    assert _name_sim("John Doe", "John Doe") == 1.0


def test_name_sim_case_insensitive():
    assert _name_sim("JOHN DOE", "john doe") == 1.0


def test_name_sim_word_order():
    score = _name_sim("Doe John", "John Doe")
    assert score >= 0.95


def test_handle_sim_strips_at():
    score = _handle_sim("@john_doe", "john_doe")
    assert score >= 0.95


def test_extract_urls_finds_domain():
    urls = _extract_urls("Check my site https://john.com/portfolio")
    assert "john.com/portfolio" in urls


def test_extract_urls_empty_bio():
    assert _extract_urls(None) == set()
    assert _extract_urls("") == set()


# ── score_pair ────────────────────────────────────────────────────────────────

def test_high_confidence_same_name_and_url():
    match = score_pair(**_pair(
        source_display_name="Chidi Okeke",
        source_username="chidiokeke",
        source_bio="Designer. https://chidi.design",
        target_display_name="Chidi Okeke",
        target_username="chidi.okeke",
        target_bio="Product designer. https://chidi.design",
    ))
    assert match is not None
    assert match.confidence >= AUTO_CONFIRM_THRESHOLD
    assert match.status == "confirmed"


def test_medium_confidence_goes_to_review():
    match = score_pair(**_pair(
        source_display_name="Ada Okonkwo",
        target_display_name="Ada Okonkwo",
    ))
    assert match is not None
    assert REVIEW_THRESHOLD <= match.confidence < AUTO_CONFIRM_THRESHOLD
    assert match.status == "pending"


def test_low_confidence_returns_none():
    match = score_pair(**_pair(
        source_display_name="Emeka",
        target_display_name="Bola",
    ))
    assert match is None


def test_no_signals_returns_none():
    match = score_pair(**_pair())
    assert match is None


def test_shared_url_contributes():
    match_with_url = score_pair(**_pair(
        source_display_name="Tunde Bello",
        target_display_name="Tunde Bello",
        source_bio="https://tunde.com",
        target_bio="https://tunde.com",
    ))
    match_without = score_pair(**_pair(
        source_display_name="Tunde Bello",
        target_display_name="Tunde Bello",
    ))
    assert match_with_url is not None
    assert match_without is not None
    assert match_with_url.confidence > match_without.confidence


def test_match_method_lists_signals():
    match = score_pair(**_pair(
        source_display_name="Ngozi Eze",
        source_bio="https://ngozi.io",
        target_display_name="Ngozi Eze",
        target_bio="Visit https://ngozi.io",
    ))
    assert match is not None
    assert "name" in match.match_method
    assert "bio_url" in match.match_method


def test_confidence_capped_at_one():
    match = score_pair(**_pair(
        source_display_name="Identical Person",
        source_username="identicalperson",
        source_bio="Bio text here https://same.com",
        target_display_name="Identical Person",
        target_username="identicalperson",
        target_bio="Bio text here https://same.com",
    ))
    assert match is not None
    assert match.confidence <= 1.0
