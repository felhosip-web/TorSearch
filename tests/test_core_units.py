"""
Comprehensive unit tests for:
- detect_language
- detect_category
- matches_precise_filter
- parse_list
- ConfigManager & AppConfig
- TkLogHandler & standard logging integration
"""
import logging
import tempfile
import tkinter as tk
from pathlib import Path
import pytest
from bs4 import BeautifulSoup

from onion_search.config import AppConfig, ConfigManager
from onion_search.core.detector import (
    decode_base58,
    detect_category,
    detect_language,
    extract_bitcoin_addresses,
    extract_fingerprint,
    is_valid_base58_address,
    is_valid_bech32_address,
)
from onion_search.ui.filters import matches_precise_filter
from onion_search.ui.log_panel import LogPanel, TkLogHandler, logger
from onion_search.utils.helpers import fmt_ts, parse_list


# ==========================================
# 1. Unit Tests for parse_list
# ==========================================
def test_parse_list_empty():
    assert parse_list("") == []
    assert parse_list(None) == []
    assert parse_list("   ") == []


def test_parse_list_valid():
    raw = "forum, wiki,  library , Market"
    parsed = parse_list(raw)
    assert parsed == ["forum", "wiki", "library", "market"]


def test_parse_list_single():
    assert parse_list("HUN") == ["hun"]


# ==========================================
# 2. Unit Tests for detect_language
# ==========================================
def test_detect_language_html_attr_fast_path():
    assert detect_language("Unrelated text", html_lang_attr="hu") == "hu"
    assert detect_language("Unrelated text", html_lang_attr="de-DE") == "de"
    assert detect_language("Unrelated text", html_lang_attr="FR") == "fr"
    assert detect_language("Unrelated text", html_lang_attr="ru") == "ru"


def test_detect_language_hungarian():
    hu_text = "Ez egy nagyon szép és hasznos magyar weboldal a biztonságról és a hálózatokról hogy segítsen."
    assert detect_language(hu_text) == "hu"


def test_detect_language_english():
    en_text = "This is a detailed overview of the network infrastructure and the history of modern computing."
    assert detect_language(en_text) == "en"


def test_detect_language_german():
    de_text = "Das ist ein deutsches Diskussionsforum und die Beiträge sind sehr informativ und nützlich."
    assert detect_language(de_text) == "de"


def test_detect_language_russian():
    ru_text = "Привет мир это информационный ресурс и полезный сайт на русском языке для всех пользователей."
    assert detect_language(ru_text) == "ru"


def test_detect_language_fallback():
    assert detect_language("12345 67890 !?#") in ("en", "hu", "de", "ru")


# ==========================================
# 3. Unit Tests for detect_category
# ==========================================
def test_detect_category_forum():
    title = "Hacker Board"
    text = "Welcome to phpBB forum bulletin board discussions and topics reply to thread"
    assert detect_category(title, text) == "forum"


def test_detect_category_wiki():
    title = "Onion Encyclopedia"
    text = "MediaWiki special:search main page - wiki edit this page and revision history"
    assert detect_category(title, text) == "wiki"


def test_detect_category_library():
    title = "Digital Archive"
    text = "Genesis ebooks catalog z-library books catalog author isbn download pdf monograph"
    assert detect_category(title, text) == "library"


def test_detect_category_market():
    title = "Silk Shop"
    text = "Marketplace vendor escrow shopping cart add to cart btc price checkout shipping"
    assert detect_category(title, text) == "market"


def test_detect_category_news():
    title = "Global Dispatch"
    text = "Daily news journalism breaking news correspondent reporter editorial press release"
    assert detect_category(title, text) == "news"


def test_detect_category_structural_soup():
    html_forum = "<html><head><title>Board</title></head><body><form><textarea name='message'></textarea><input type='submit' value='Reply'></form></body></html>"
    soup = BeautifulSoup(html_forum, "html.parser")
    cat = detect_category("Board", "User discussion", soup=soup)
    assert cat == "forum"


# ==========================================
# 4. Unit Tests for matches_precise_filter
# ==========================================
def test_matches_precise_filter_disabled():
    ok, reason = matches_precise_filter(
        title="Title", text="Text", enabled=False, must_all="missing_keyword"
    )
    assert ok is True
    assert reason == "OK"


def test_matches_precise_filter_must_all():
    title = "Security Guide"
    text = "encryption privacy and network anonymity"

    # Match all passes
    ok, _ = matches_precise_filter(
        title, text, enabled=True, must_all="security, encryption"
    )
    assert ok is True

    # Missing one fails
    ok, reason = matches_precise_filter(
        title, text, enabled=True, must_all="security, bitcoin"
    )
    assert ok is False
    assert "hiányzik MUST ALL" in reason


def test_matches_precise_filter_must_any():
    title = "Hardware Store"
    text = "laptops, desktops and monitors for sale"

    # At least one matches
    ok, _ = matches_precise_filter(
        title, text, enabled=True, must_any="phones, laptops"
    )
    assert ok is True

    # None matches
    ok, reason = matches_precise_filter(
        title, text, enabled=True, must_any="cars, bicycles"
    )
    assert ok is False
    assert "egyik ANY sem talalhato" in reason


def test_matches_precise_filter_must_not():
    title = "Legit Services"
    text = "quality goods with fast delivery"

    # Forbidden word absent
    ok, _ = matches_precise_filter(
        title, text, enabled=True, must_not="scam, fraud"
    )
    assert ok is True

    # Forbidden word present
    ok, reason = matches_precise_filter(
        title, text + " this is a scam site", enabled=True, must_not="scam"
    )
    assert ok is False
    assert "kizart NOT talalat" in reason


def test_matches_precise_filter_title_and_regex():
    title = "Tor Hidden Wiki"
    text = "Comprehensive directory of onion services verified 2026."

    # Title match
    ok, _ = matches_precise_filter(
        title, text, enabled=True, title_contains="Hidden Wiki"
    )
    assert ok is True

    # Title mismatch
    ok, reason = matches_precise_filter(
        title, text, enabled=True, title_contains="Marketplace"
    )
    assert ok is False

    # Regex match
    ok, _ = matches_precise_filter(
        title, text, enabled=True, regex=r"verified\s+\d{4}"
    )
    assert ok is True


# ==========================================
# 5. Unit Tests for ConfigManager & AppConfig
# ==========================================
def test_config_manager_defaults():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        mgr = ConfigManager(config_file=cfg_path)
        assert mgr.config.socks_port == "9050"
        assert mgr.config.workers == 6
        assert mgr.config.dark_mode is True


def test_config_manager_save_and_reload():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        mgr = ConfigManager(config_file=cfg_path)
        
        # Modify and save
        mgr.config.workers = 10
        mgr.config.socks_port = "9150"
        mgr.config.dark_mode = False
        assert mgr.save() is True

        # Reload with separate manager instance
        reloaded_mgr = ConfigManager(config_file=cfg_path)
        assert reloaded_mgr.config.workers == 10
        assert reloaded_mgr.config.socks_port == "9150"
        assert reloaded_mgr.config.dark_mode is False


# ==========================================
# 6. Unit Tests for TkLogHandler & Logging
# ==========================================
def test_tk_log_handler_integration():
    root = tk.Tk()
    root.withdraw()

    log_panel = LogPanel(root)
    test_logger = logging.getLogger("test_onion_search")
    test_logger.setLevel(logging.INFO)
    handler = TkLogHandler(log_panel)
    test_logger.addHandler(handler)

    test_logger.info("[OK] Integration test message")
    test_logger.error("Critical test error occurred")
    root.update()

    assert any("[OK] Integration test message" in msg for msg, _ in log_panel.log_history)
    assert any("Critical test error occurred" in msg for msg, _ in log_panel.log_history)

    root.destroy()
