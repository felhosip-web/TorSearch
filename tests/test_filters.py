import pytest
from onion_search.ui.filters import matches_precise_filter

def test_matches_precise_filter_disabled():
    ok, reason = matches_precise_filter(
        title="Any Title",
        text="Any content",
        enabled=False,
        must_all="specific",
    )
    assert ok is True

def test_matches_precise_filter_must_all():
    ok, _ = matches_precise_filter(
        title="Tor Onion Hub",
        text="Welcome to the onion hub discussion",
        enabled=True,
        must_all="tor, hub",
    )
    assert ok is True

    ok, reason = matches_precise_filter(
        title="Tor Onion Hub",
        text="Welcome to the onion hub discussion",
        enabled=True,
        must_all="tor, bitcoin",
    )
    assert ok is False
    assert "bitcoin" in reason

def test_matches_precise_filter_must_any():
    ok, _ = matches_precise_filter(
        title="Crypto Page",
        text="We accept monero or zcash",
        enabled=True,
        must_any="bitcoin, monero",
    )
    assert ok is True

    ok, reason = matches_precise_filter(
        title="Crypto Page",
        text="We accept ethereum only",
        enabled=True,
        must_any="bitcoin, monero",
    )
    assert ok is False

def test_matches_precise_filter_must_not():
    ok, reason = matches_precise_filter(
        title="Market",
        text="Buy scam goods here",
        enabled=True,
        must_not="scam, fake",
    )
    assert ok is False
    assert "scam" in reason

def test_matches_precise_filter_title_and_regex():
    ok, _ = matches_precise_filter(
        title="Official Forum",
        text="Contact support: user@example.com",
        enabled=True,
        title_contains="forum",
        regex=r"[\w\.-]+@[\w\.-]+",
        min_len=10,
    )
    assert ok is True
