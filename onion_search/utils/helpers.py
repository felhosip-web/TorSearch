"""
Helper utilities and configuration constants.
"""
from datetime import datetime
from pathlib import Path

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"},
]
TIMEOUT_GET = 20

STATE_DIR = Path.home() / ".config" / "onion_search"
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "state_v3.json"
DEAD_FILE = STATE_DIR / "dead_blacklist.json"
DB_FILE = STATE_DIR / "onion.db"

GITHUB_SOURCES = [
    "https://raw.githubusercontent.com/alecmuffett/real-world-onion-sites/master/real-world-onion-sites.txt"
]


def fmt_ts(ts):
    """Format Unix timestamp float into YYYY-MM-DD HH:MM string."""
    try:
        if not ts:
            return ""
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


def parse_list(s):
    """Parse comma-separated text into a list of stripped, lower-case strings."""
    if not s:
        return []
    return [p.strip().lower() for p in s.split(",") if p.strip()]
