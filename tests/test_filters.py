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
        use_regex=True,
    )
    assert ok is True


def test_matches_precise_filter_regex_injection_escaping():
    # User types special characters like [test] or c++ or (a|b) without regex mode
    ok, _ = matches_precise_filter(
        title="C++ Forum",
        text="Welcome to the c++ discussion board (special [tag])",
        enabled=True,
        must_all="c++, [tag]",
        must_not="nonexistent(item)",
        use_regex=False,
    )
    assert ok is True


def test_matches_precise_filter_invalid_regex_and_redos_guard():
    # Invalid regex syntax in regex mode
    ok, reason = matches_precise_filter(
        title="Test",
        text="Sample text",
        enabled=True,
        must_all="[unclosed_bracket",
        use_regex=True,
    )
    assert ok is False
    assert "regex hiba" in reason

    # Excessively long regex (>250 chars) ReDoS guard
    long_pat = "a" * 260
    ok, reason = matches_precise_filter(
        title="Test",
        text="Sample text",
        enabled=True,
        must_all=long_pat,
        use_regex=True,
    )
    assert ok is False
    assert "Túl hosszú regex" in reason
