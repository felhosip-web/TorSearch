"""
Helper utilities, formatting, and string parsing functions with full type annotations.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from onion_search.config import (
    CONFIG_DIR,
    DB_FILE,
    DEFAULT_DEAD_FILE,
    DEFAULT_SEEDS_FILE,
    DEFAULT_STATE_FILE,
    DEFAULT_TIMEOUT_GET,
    STATE_DIR,
)

HEADERS_LIST: List[Dict[str, str]] = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"},
]
TIMEOUT_GET: int = DEFAULT_TIMEOUT_GET
STATE_FILE: Path = DEFAULT_STATE_FILE
DEAD_FILE: Path = DEFAULT_DEAD_FILE
SEEDS_FILE: Path = DEFAULT_SEEDS_FILE

# Primary seed sources: GitHub, Tor66, Deep Search, Ahmia, OnionSearchEngine
GITHUB_SOURCES: List[str] = [
    "https://raw.githubusercontent.com/alecmuffett/real-world-onion-sites/master/real-world-onion-sites.txt",
    "https://raw.githubusercontent.com/DanMcInerney/onion-urls/master/onion-urls.txt",
]

TOR66_SOURCES: Dict[str, str] = {
    "onion": "http://tor66sewebgixwhcqfnpq5wfsqxuvhn2bawa4rwfdgahforacxdad123.onion/fresh",
    "clearnet": "https://tor66.org/fresh",
    "clearnet_alt": "https://tor66.org/",
}

DEEPSEARCH_SOURCES: Dict[str, str] = {
    "onion": "http://deepsearch74sxv42abcdefghijklmnopqrstuvwxyz234567abcdefg.onion/fresh",
    "clearnet": "https://deepsearch.onion.pet/fresh",
    "clearnet_alt": "https://deepsearch.net/links",
}

AHMIA_SOURCES: Dict[str, str] = {
    "onion": "http://juhanurmih5wu7bv5imwtvfera6qnfd4hxxstl7tggdd2ufdgxao4yd.onion/onions/",
    "clearnet": "https://ahmia.fi/onions/",
}

OSE_SOURCES: Dict[str, str] = {
    "clearnet": "https://onionsearchengine.com/search.php?search=wiki",
}


def fmt_ts(ts: Optional[Union[float, int, str]]) -> str:
    """Format Unix timestamp into 'YYYY-MM-DD HH:MM' string."""
    try:
        if not ts:
            return ""
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def parse_list(s: Optional[str]) -> List[str]:
    """Parse comma-separated text into a list of stripped, lower-case strings."""
    if not s:
        return []
    return [p.strip().lower() for p in s.split(",") if p.strip()]
