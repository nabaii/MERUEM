"""Tests for entity_extractor — Nigerian brand / location rule-based matching."""

from app.processing.entity_extractor import extract_entities


def test_extracts_hashtags():
    result = extract_entities("#Lagos #Afrobeats great vibes")
    assert "Lagos" in result["hashtags"]
    assert "Afrobeats" in result["hashtags"]


def test_extracts_mentions():
    result = extract_entities("Thanks @GTBank for the swift transfer!")
    assert "GTBank" in result["mentions"]


def test_detects_nigerian_brand():
    result = extract_entities("Just opened my Kuda account — seamless!")
    assert "Kuda" in result["nigerian_brands"]


def test_detects_multiple_brands():
    result = extract_entities("Flutterwave and Paystack are changing fintech in Nigeria")
    brands = result["nigerian_brands"]
    assert "Flutterwave" in brands
    assert "Paystack" in brands


def test_detects_nigerian_city():
    result = extract_entities("Born and raised in Lagos, moving to Abuja next month")
    locs = result["nigerian_locations"]
    assert "Lagos" in locs
    assert "Abuja" in locs


def test_empty_text():
    result = extract_entities("")
    assert result["hashtags"] == []
    assert result["nigerian_brands"] == []
    assert result["nigerian_locations"] == []


def test_no_false_positives_on_foreign_text():
    result = extract_entities("The quick brown fox jumps over the lazy dog")
    assert result["nigerian_brands"] == []
    assert result["nigerian_locations"] == []
