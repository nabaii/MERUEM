"""Tests for text_cleaner module — no external model dependencies."""

from app.processing.text_cleaner import (
    clean_text,
    detect_language,
    extract_hashtags,
    is_retweet,
    strip_mentions,
    strip_urls,
)


def test_strip_urls():
    assert strip_urls("Check this out https://t.co/abc123 now") == "Check this out  now"
    assert strip_urls("No URL here") == "No URL here"


def test_strip_mentions():
    assert strip_mentions("Hey @BudweiserNG great ad!") == "Hey  great ad!"
    assert strip_mentions("No mentions") == "No mentions"


def test_clean_text_full_pipeline():
    raw = "RT @Paystack: New feature 🚀 https://t.co/xyz #Fintech great stuff!"
    cleaned = clean_text(raw)
    assert "https://" not in cleaned
    assert "@Paystack" not in cleaned
    assert "#Fintech" in cleaned  # hashtags are preserved
    assert cleaned.strip() == cleaned  # no leading/trailing whitespace


def test_is_retweet():
    assert is_retweet("RT @SomeUser: This is a retweet")
    assert is_retweet("rt @someone: lowercase")
    assert not is_retweet("Just a regular tweet about Lagos")
    assert not is_retweet("")


def test_extract_hashtags():
    tags = extract_hashtags("Love #Lagos #Afrobeats vibes! #naija")
    assert "#lagos" in tags
    assert "#afrobeats" in tags
    assert "#naija" in tags
    assert len(tags) == 3


def test_detect_language_english():
    lang = detect_language("This is a great day in Lagos, Nigeria today!")
    assert lang in ("en", "unknown")  # langdetect may vary


def test_detect_language_pidgin():
    pidgin = "Oya abeg make dem comot wahala from here, omo this no be right"
    lang = detect_language(pidgin)
    assert lang in ("pcm", "en")  # detected as Pidgin or close English


def test_detect_language_short_text():
    # Too short to detect reliably
    lang = detect_language("Hi")
    assert lang == "unknown"


def test_clean_preserves_hashtags():
    raw = "Big news from #GTBank and #Flutterwave today"
    cleaned = clean_text(raw)
    assert "#GTBank" in cleaned
    assert "#Flutterwave" in cleaned
