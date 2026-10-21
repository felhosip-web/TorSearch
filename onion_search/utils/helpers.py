# Copyright 2026 HES Projects by FePe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Helper utilities, formatting, and string parsing functions with full type annotations.
Developed by HES Projects by FePe.
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

import random

# Fix Firefox ESR / Windows 10 Tor Browser profile headers
# Megjegyzés: Időnként frissítendő a legfrissebb Tor Browser ESR verzió szerint.
TOR_BROWSER_UA: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
}

HEADERS_LIST: List[Dict[str, str]] = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"},
]


def get_request_headers(rotate: bool = False) -> Dict[str, str]:
    """
    Return standard request headers.
    If rotate is True, selects a random header set from HEADERS_LIST.
    If rotate is False, returns the uniform TOR_BROWSER_UA profile.
    """
    if rotate:
        return dict(random.choice(HEADERS_LIST))
    return dict(TOR_BROWSER_UA)
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

# 3. Haystak
HAYSTAK_SOURCES: Dict[str, str] = {
    "onion": "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/?q=wiki",
    "clearnet": "https://haystak.onion.pet/?q=wiki",
    "clearnet_alt": "https://haystak.onion.ws/?q=wiki",
}

# 4. OnionLand
ONIONLAND_SOURCES: Dict[str, str] = {
    "onion": "http://onionland74v76h2n74i3w6u6v2o6q6w7x2k4y2b5a2c3d4e5f6g7h8ij.onion/search?q=hidden",
    "clearnet": "https://onionlandsearchengine.com/search?q=wiki",
    "clearnet_alt": "https://onionland.onion.pet/search?q=wiki",
}

# 7. Torch
TORCH_SOURCES: Dict[str, str] = {
    "onion": "http://xmh57jrknzkhv6y3ls3ubitzfqnkrwxhopf5aygthi7d6rfdvgchu6qd.onion/cgi-bin/omega/omega?P=wiki",
    "clearnet": "https://torch.onion.pet/cgi-bin/omega/omega?P=wiki",
}

# 8. not Evil (last resort)
NOTEVIL_SOURCES: Dict[str, str] = {
    "onion": "http://hss3uro2hsxfogfq.onion/index.php?q=wiki",
    "clearnet": "https://notevil.onion.pet/?q=wiki",
}

# Priority sequence for seed fallback cascades
DEFAULT_SEED_PRIORITY: List[str] = [
    "tor66",
    "deepsearch",
    "haystak",
    "onionland",
    "github",
    "ose",
    "torch",
    "notevil",
]

# Minimum acceptable yield from a single provider before triggering fallback to next
MIN_SEED_YIELD_THRESHOLD: int = 10


def fmt_ts(ts: Optional[Union[float, int, str]]) -> str:
    """Format Unix timestamp into 'YYYY-MM-DD HH:MM' string."""
    try:
        if not ts:
            return ""
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


import os

def ensure_private_dir(path: Union[str, Path]) -> None:
    """Ensure directory exists with 0o700 permissions."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(p, 0o700)
    except Exception:
        pass


def secure_write_text(path: Union[str, Path], text: str, encoding: str = "utf-8") -> None:
    """Write text to file securely using atomic creation/truncation with 0o600 permissions."""
    p = Path(path)
    ensure_private_dir(p.parent)
    data = text.encode(encoding)

    # Write atomically via temp file with O_CREAT|O_WRONLY|O_TRUNC and 0o600 mode
    tmp_path = p.with_suffix(f"{p.suffix}.tmp.{os.getpid()}")
    try:
        fd = os.open(tmp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except Exception:
            pass
        os.replace(tmp_path, p)
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
        raise


def parse_list(s: Optional[str]) -> List[str]:
    """Parse comma-separated text into a list of stripped, lower-case strings."""
    if not s:
        return []
    return [p.strip().lower() for p in s.split(",") if p.strip()]


import re
from urllib.parse import urlparse

ONION_HOST_REGEX: re.Pattern[str] = re.compile(r"^[a-z2-7]{16,56}\.onion$", re.IGNORECASE)


def is_onion_host(url: str) -> bool:
    """
    Check if the URL hostname strictly ends with '.onion'.
    Returns True only if hostname is non-empty, lowercased, and ends with '.onion'.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        hostname = (urlparse(url).hostname or "").strip().lower()
        return bool(hostname and hostname.endswith(".onion"))
    except Exception:
        return False


def normalize_onion_url(url: str, host_only: bool = False) -> Optional[str]:
    """
    Normalize and validate .onion URLs according to strict criteria:
    - Always uses http:// scheme
    - Hostname is lowercased
    - Trailing slash removed from path
    - Query string and fragment dropped
    - Only valid .onion domains accepted
    - Returns 'http://hostname.onion' if path is empty/root or if host_only is True
    """
    if not url or not isinstance(url, str):
        return None

    s = url.strip()
    if not s:
        return None

    # Handle scheme-less URLs if passed (e.g. "abc...onion/path")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+-.]*://", s):
        s = "http://" + s

    try:
        parsed = urlparse(s)
    except Exception:
        return None

    host = (parsed.hostname or "").strip().lower()
    if not host or not ONION_HOST_REGEX.match(host):
        return None

    if host_only:
        return f"http://{host}"

    path = parsed.path or ""
    # Strip trailing slashes
    while len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    if path in ("", "/"):
        return f"http://{host}"

    if not path.startswith("/"):
        path = "/" + path

    return f"http://{host}{path}"
