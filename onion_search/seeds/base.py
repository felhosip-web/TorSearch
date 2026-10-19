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
Base Abstract Seed Plugin Interface.
Defines common lifecycle, health checking with TTL caching, status tracking,
and network helper utilities for seed discovery plugins.
Developed by HES Projects by FePe.
"""
from abc import ABC, abstractmethod
import logging
import random
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from onion_search.utils.helpers import HEADERS_LIST, normalize_onion_url

logger = logging.getLogger("onion_search")
ONION_REGEX = re.compile(
    r"\b(?:https?://)?([a-z2-7]{16,56}\.onion)(?:/[^\s\"'<>]*)?", re.IGNORECASE
)


def extract_onion_urls_from_text(text: str) -> Set[str]:
    """Extract and normalize all valid .onion URLs from raw text/HTML."""
    found: Set[str] = set()
    if not text:
        return found
    for match in ONION_REGEX.finditer(text):
        raw_match = match.group(0)
        norm = normalize_onion_url(raw_match)
        if norm:
            found.add(norm)
    return found


class BaseSeedPlugin(ABC):
    """
    Abstract base class for all seed discovery plugins.

    Subclasses must define:
    - id: Unique string identifier (e.g., 'tor66')
    - name: Human-readable display name
    - priority: Integer priority for cascade execution (lower number = earlier execution)
    - _do_fetch_seeds(query, proxy_url, allow_clearnet, timeout)
    """

    id: str = "base_plugin"
    name: str = "Base Seed Plugin"
    priority: int = 100
    enabled: bool = True
    timeout: int = 15
    max_retries: int = 1
    user_agent: Optional[str] = None
    health_cache_ttl: float = 600.0  # Default 10 minutes cache TTL for health check

    def __init__(self) -> None:
        self.last_success: float = 0.0
        self.last_error: Optional[str] = None
        self.last_seed_count: int = 0
        self._health_status: Optional[Tuple[bool, str]] = None
        self._health_last_check: float = 0.0

    def _make_request(
        self,
        url: str,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: Optional[int] = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
    ) -> Optional[requests.Response]:
        """
        Execute HTTP request enforcing Tor proxy security policy.
        """
        req_timeout = timeout or self.timeout
        is_onion = ".onion" in url

        if is_onion and not proxy_url:
            logger.warning(
                f"[SECURITY] Plugin '{self.id}': .onion URL skipped (no Tor proxy): {url}"
            )
            return None

        if not is_onion and not allow_clearnet and not proxy_url:
            logger.warning(
                f"[SECURITY] Plugin '{self.id}': Clearnet URL blocked by Tor-only protection: {url}"
            )
            return None

        proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        req_headers = headers.copy() if headers else {}
        if "User-Agent" not in req_headers:
            if self.user_agent:
                req_headers["User-Agent"] = self.user_agent
            else:
                req_headers.update(random.choice(HEADERS_LIST))

        for attempt in range(self.max_retries + 1):
            try:
                if method.upper() == "HEAD":
                    r = requests.head(
                        url, timeout=req_timeout, headers=req_headers, proxies=proxies
                    )
                else:
                    r = requests.get(
                        url, timeout=req_timeout, headers=req_headers, proxies=proxies
                    )
                return r
            except Exception as e:
                logger.debug(
                    f"[SEED PLUGIN '{self.id}'] Request failed ({url}, attempt {attempt + 1}): {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(1.0)
        return None

    def fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: Optional[int] = None,
    ) -> Set[str]:
        """
        Public entrypoint to fetch seed URLs from this plugin with safety,
        logging, and status tracking.
        """
        if not self.enabled:
            logger.info(f"[SEED PLUGIN '{self.id}'] Plugin Disabled — skipping.")
            return set()

        start_ts = time.time()
        logger.info(f"[SEED PLUGIN '{self.id}'] Starting seed fetch...")
        try:
            seeds = self._do_fetch_seeds(
                query=query,
                proxy_url=proxy_url,
                allow_clearnet=allow_clearnet,
                timeout=timeout or self.timeout,
            )
            count = len(seeds)
            self.last_seed_count = count
            self.last_success = time.time()
            self.last_error = None
            elapsed = time.time() - start_ts
            logger.info(
                f"[SEED PLUGIN '{self.id}'] Yielded {count} seeds in {elapsed:.2f}s"
            )
            return seeds
        except Exception as e:
            err_msg = str(e)
            self.last_error = err_msg
            logger.error(
                f"[SEED PLUGIN '{self.id}'] Error fetching seeds: {err_msg}",
                exc_info=True,
            )
            return set()

    def health_check(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        force: bool = False,
    ) -> Tuple[bool, str]:
        """
        Public health check method with TTL-based caching to prevent spamming sources.
        """
        now = time.time()
        if (
            not force
            and self._health_status is not None
            and (now - self._health_last_check) < self.health_cache_ttl
        ):
            return self._health_status

        logger.debug(f"[SEED PLUGIN '{self.id}'] Performing fast health check...")
        try:
            ok, msg = self._do_health_check(
                proxy_url=proxy_url, allow_clearnet=allow_clearnet
            )
            self._health_status = (ok, msg)
            self._health_last_check = now
            if ok:
                self.last_error = None
            else:
                self.last_error = msg
            return ok, msg
        except Exception as e:
            err_msg = f"Health check exception: {e}"
            self._health_status = (False, err_msg)
            self._health_last_check = now
            self.last_error = err_msg
            return False, err_msg

    @abstractmethod
    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        """Plugin implementation for seed discovery."""
        pass

    def _do_health_check(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Tuple[bool, str]:
        """
        Default lightweight health check: attempts a fast request to the primary endpoint.
        Plugins can override this method for custom health check logic.
        """
        endpoint = self.get_primary_endpoint(
            proxy_url=proxy_url, allow_clearnet=allow_clearnet
        )
        if not endpoint:
            return False, "Nincs megadható végpont (Tor proxy hiányzik vagy clearnet tiltva)"

        resp = self._make_request(
            endpoint,
            proxy_url=proxy_url,
            allow_clearnet=allow_clearnet,
            timeout=8,
            method="HEAD",
        )
        if not resp or resp.status_code not in (200, 301, 302):
            # Try GET if HEAD was disallowed
            resp = self._make_request(
                endpoint,
                proxy_url=proxy_url,
                allow_clearnet=allow_clearnet,
                timeout=8,
                method="GET",
            )

        if resp and resp.status_code in (200, 301, 302):
            return True, f"Elérhető ({resp.status_code} OK)"
        elif resp:
            return False, f"Hibás status code: HTTP {resp.status_code}"
        else:
            return False, "Nem érkezett válasz (Timeout vagy hálózati hiba)"

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        """Return the primary endpoint URL for health checking or default fetching."""
        return None
