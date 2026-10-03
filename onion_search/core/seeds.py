"""
Multi-source automated seed discovery and synchronization.
Integrates Tor66, Deep Search, Ahmia, GitHub and OnionSearchEngine lists
with local JSON cache persistence and strict Tor proxy routing.
"""
import json
import logging
from pathlib import Path
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

from onion_search.utils.helpers import (
    AHMIA_SOURCES,
    DEEPSEARCH_SOURCES,
    GITHUB_SOURCES,
    HEADERS_LIST,
    OSE_SOURCES,
    SEEDS_FILE,
    TIMEOUT_GET,
    TOR66_SOURCES,
)

logger = logging.getLogger("onion_search")
ONION_REGEX = re.compile(r"\b([a-z2-7]{16,56})\.onion\b", re.IGNORECASE)


def extract_onion_urls(text: str) -> Set[str]:
    """Extract and normalize all valid .onion URLs from raw text/HTML."""
    found: Set[str] = set()
    if not text:
        return found
    for match in ONION_REGEX.finditer(text):
        m_lower = match.group(1).lower()
        found.add(f"http://{m_lower}.onion")
    return found


class SeedManager:
    """Coordinates fetching and caching .onion seeds across multiple providers."""

    def __init__(self, cache_file: Path = SEEDS_FILE) -> None:
        self.cache_file = Path(cache_file)
        self.last_update_ts: float = 0.0
        self.cached_seeds: Set[str] = set()
        self.load_cache()

    def load_cache(self) -> Set[str]:
        """Load persistent seed cache from disk."""
        if not self.cache_file.exists():
            return set()
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.last_update_ts = float(data.get("updated_at", 0))
                urls = set(data.get("seeds", []))
                self.cached_seeds = urls
                return urls
        except Exception as e:
            logger.warning(f"[SEED] Cache betöltési hiba: {e}")
            return set()

    def save_cache(
        self,
        seeds: Set[str],
        source_counts: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Save discovered seed URLs to persistent cache file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.last_update_ts = time.time()
            self.cached_seeds = set(seeds)
            payload = {
                "updated_at": self.last_update_ts,
                "total_count": len(self.cached_seeds),
                "source_counts": source_counts or {},
                "seeds": sorted(list(self.cached_seeds)),
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"[SEED] Cache mentési hiba: {e}")
            return False

    def is_update_due(self, interval_hours: float = 12.0) -> bool:
        """Determine if an automatic seed update is due."""
        if not self.cached_seeds or self.last_update_ts == 0:
            return True
        elapsed_hours = (time.time() - self.last_update_ts) / 3600.0
        return elapsed_hours >= interval_hours

    def _make_request(
        self,
        url: str,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Optional[str]:
        """Execute HTTP request enforcing Tor proxy policy."""
        is_onion = ".onion" in url
        if is_onion and not proxy_url:
            logger.warning(f"[SECURITY] .onion seed forrás kihagyva, mert nincs Tor proxy: {url}")
            return None

        if not is_onion and not allow_clearnet and not proxy_url:
            logger.warning(f"[SECURITY] Clearnet seed forrás blokkolva Tor-only védelem miatt: {url}")
            return None

        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        headers = random.choice(HEADERS_LIST)
        try:
            r = requests.get(url, timeout=timeout, headers=headers, proxies=proxies)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            logger.debug(f"[SEED] Lekérési hiba ({url}): {e}")
        return None

    def fetch_tor66(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """
        Fetch fresh onion seeds from Tor66 hidden service directory.
        Tries Tor66 .onion service first if proxy is active, then clearnet mirror.
        """
        found: Set[str] = set()
        endpoints = []
        if proxy_url:
            endpoints.append(TOR66_SOURCES["onion"])
        if allow_clearnet or proxy_url:
            endpoints.append(TOR66_SOURCES["clearnet"])
            endpoints.append(TOR66_SOURCES["clearnet_alt"])

        for ep in endpoints:
            text = self._make_request(
                ep, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=18
            )
            if text:
                urls = extract_onion_urls(text)
                found.update(urls)
                if len(found) > 10:
                    break
        return found

    def fetch_deepsearch(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """
        Fetch onion seeds from Deep Search directory and search endpoints.
        """
        found: Set[str] = set()
        endpoints = []
        if proxy_url:
            endpoints.append(DEEPSEARCH_SOURCES["onion"])
        if allow_clearnet or proxy_url:
            endpoints.append(DEEPSEARCH_SOURCES["clearnet"])
            endpoints.append(DEEPSEARCH_SOURCES["clearnet_alt"])

        for ep in endpoints:
            text = self._make_request(
                ep, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=18
            )
            if text:
                urls = extract_onion_urls(text)
                found.update(urls)
                if len(found) > 10:
                    break
        return found

    def fetch_ahmia(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered onions from Ahmia index list."""
        endpoints = []
        if proxy_url:
            endpoints.append(AHMIA_SOURCES["onion"])
        if allow_clearnet or proxy_url:
            endpoints.append(AHMIA_SOURCES["clearnet"])

        for ep in endpoints:
            text = self._make_request(
                ep, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=15
            )
            if text:
                return extract_onion_urls(text)
        return set()

    def fetch_github(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch vetted .onion collections from curated GitHub repositories."""
        found: Set[str] = set()
        for src in GITHUB_SOURCES:
            text = self._make_request(
                src, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=15
            )
            if text:
                found.update(extract_onion_urls(text))
        return found

    def fetch_ose(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered onion sites from OnionSearchEngine."""
        ep = OSE_SOURCES.get("clearnet")
        if not ep:
            return set()
        text = self._make_request(
            ep, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=15
        )
        if text:
            return extract_onion_urls(text)
        return set()

    def fetch_all(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        selected_sources: Optional[List[str]] = None,
        on_source_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[Set[str], Dict[str, int]]:
        """
        Query all configured providers (Tor66, Deep Search, Ahmia, GitHub, OnionSearchEngine).
        Returns combined deduplicated seeds set and individual source statistics.
        """
        sources_to_run = selected_sources or ["tor66", "deepsearch", "ahmia", "github", "ose"]
        source_counts: Dict[str, int] = {}
        all_found: Set[str] = set()

        source_dispatch: Dict[str, Callable[[], Set[str]]] = {
            "tor66": lambda: self.fetch_tor66(proxy_url=proxy_url, allow_clearnet=allow_clearnet),
            "deepsearch": lambda: self.fetch_deepsearch(proxy_url=proxy_url, allow_clearnet=allow_clearnet),
            "ahmia": lambda: self.fetch_ahmia(proxy_url=proxy_url, allow_clearnet=allow_clearnet),
            "github": lambda: self.fetch_github(proxy_url=proxy_url, allow_clearnet=allow_clearnet),
            "ose": lambda: self.fetch_ose(proxy_url=proxy_url, allow_clearnet=allow_clearnet),
        }

        for src_name in sources_to_run:
            fetch_fn = source_dispatch.get(src_name)
            if not fetch_fn:
                continue
            try:
                seeds = fetch_fn()
                count = len(seeds)
                source_counts[src_name] = count
                all_found.update(seeds)
                if on_source_progress:
                    on_source_progress(src_name, count)
            except Exception as e:
                logger.error(f"[SEED] Hiba a(z) {src_name} forrás lekérésekor: {e}")
                source_counts[src_name] = 0

        # Update persistent cache
        combined = set(self.cached_seeds).union(all_found)
        self.save_cache(combined, source_counts=source_counts)
        return combined, source_counts
