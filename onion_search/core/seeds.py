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
Multi-source automated seed discovery and synchronization.
Wraps the Plugin-based SeedOrchestrator architecture for full backward compatibility
with local JSON cache persistence and strict Tor proxy routing.
Developed by HES Projects by FePe.
"""
import json
import logging
from pathlib import Path
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import requests

from onion_search.seeds.base import extract_onion_urls_from_text as extract_onion_urls
from onion_search.seeds.orchestrator import SeedOrchestrator
from onion_search.seeds.registry import PluginRegistry, registry as default_registry
from onion_search.utils.helpers import (
    DEFAULT_SEED_PRIORITY,
    HEADERS_LIST,
    MIN_SEED_YIELD_THRESHOLD,
    SEEDS_FILE,
)

logger = logging.getLogger("onion_search")


class SeedManager:
    """
    Coordinates fetching and caching .onion seeds across multiple providers
    using the Plugin Architecture and SeedOrchestrator.
    """

    def __init__(
        self,
        cache_file: Path = SEEDS_FILE,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> None:
        self.cache_file = Path(cache_file)
        self.last_update_ts: float = 0.0
        self.cached_seeds: Set[str] = set()
        self.registry = plugin_registry or default_registry
        self.orchestrator = SeedOrchestrator(plugin_registry=self.registry)
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

    def _fetch_from_plugin(
        self,
        plugin_id: str,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        query: Optional[str] = None,
    ) -> Set[str]:
        """Helper delegating fetching to a registered plugin."""
        plugin = self.registry.get_plugin(plugin_id)
        if plugin:
            return plugin.fetch_seeds(
                query=query, proxy_url=proxy_url, allow_clearnet=allow_clearnet
            )
        return set()

    def fetch_tor66(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("tor66", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_deepsearch(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("deepsearch", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_ahmia(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("ahmia", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_github(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("github", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_ose(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("ose", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_haystak(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("haystak", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_onionland(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("onionland", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_torch(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("torch", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_notevil(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        return self._fetch_from_plugin("notevil", proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_all(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        selected_sources: Optional[List[str]] = None,
        use_only_healthy: bool = False,
        min_yield_threshold: int = MIN_SEED_YIELD_THRESHOLD,
        target_total_seeds: Optional[int] = None,
        query: Optional[str] = None,
        on_source_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[Set[str], Dict[str, int]]:
        """
        Query seed providers via SeedOrchestrator priority cascade.
        Dispatches via instance methods (supporting monkeypatching/overrides).
        Updates persistent cache upon completion.
        """
        known_sources = ["tor66", "deepsearch", "haystak", "onionland", "github", "ose", "torch", "notevil", "ahmia"]
        source_dispatch = {}
        for s in known_sources:
            method = getattr(self, f"fetch_{s}", None)
            if method:
                # Capture method in default parameter
                source_dispatch[s] = (lambda m=method: m(proxy_url=proxy_url, allow_clearnet=allow_clearnet))

        all_found, source_counts = self.orchestrator.fetch_all(
            proxy_url=proxy_url,
            allow_clearnet=allow_clearnet,
            selected_sources=selected_sources,
            use_only_healthy=use_only_healthy,
            min_yield_threshold=min_yield_threshold,
            target_total_seeds=target_total_seeds,
            query=query,
            on_source_progress=on_source_progress,
            source_dispatch=source_dispatch,
        )

        # Update persistent cache
        combined = set(self.cached_seeds).union(all_found)
        self.save_cache(combined, source_counts=source_counts)
        return combined, source_counts
