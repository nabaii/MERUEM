"""Tests for location inference."""

from app.processing.location_inference import infer_location


def test_city_from_bio():
    loc = infer_location(bio="Tech entrepreneur based in Lagos, Nigeria", location_raw=None)
    assert loc == "Lagos"


def test_state_from_bio():
    loc = infer_location(bio="I live in Rivers State", location_raw=None)
    assert loc == "Rivers"


def test_city_from_raw_location():
    loc = infer_location(bio=None, location_raw="Abuja, Nigeria")
    assert loc == "Abuja"


def test_raw_location_fallback():
    # Unknown location — returns cleaned raw string
    loc = infer_location(bio=None, location_raw="Planet Earth")
    assert loc == "Planet Earth"


def test_location_from_tweet_entities():
    entities = [{"nigerian_locations": ["Port Harcourt"], "hashtags": [], "nigerian_brands": []}]
    loc = infer_location(bio=None, location_raw=None, tweet_entities_list=entities)
    assert loc == "Port Harcourt"


def test_no_location_returns_none():
    loc = infer_location(bio="Software developer", location_raw=None)
    assert loc is None


def test_bio_takes_priority_over_raw():
    loc = infer_location(bio="From Kano, Nigeria", location_raw="London UK")
    assert loc == "Kano"
