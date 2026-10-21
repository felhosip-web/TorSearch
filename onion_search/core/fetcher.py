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
High-performance network operations, async/sync fetchers, domain rate-limiting, and retry logic.
Uses lxml for 3-5x faster HTML parsing and httpx/aiohttp for async socket reuse.
Developed by HES Projects by FePe.
"""
import asyncio
from datetime import datetime
import logging
from pathlib import Path
import random
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse
import urllib.parse
import urllib.robotparser
from bs4 import BeautifulSoup
import aiohttp
import requests

from onion_search.core.detector import (
    ContentDetector,
    detect_category,
    detect_language,
    extract_bitcoin_addresses,
    extract_fingerprint,
)
from onion_search.config import MAX_RESPONSE_BYTES
from onion_search.core.seeds import SeedManager
from onion_search.utils.helpers import GITHUB_SOURCES, HEADERS_LIST, TIMEOUT_GET, is_onion_host, normalize_onion_url
from onion_search.utils.net_guard import (
    TorOnlyViolation,
    guarded_get,
    is_proxy_allowed,
)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

# Fast lxml parser detection with graceful fallback
try:
    import lxml
    HTML_PARSER = "lxml"
except ImportError:
    HTML_PARSER = "html.parser"

thread_local = threading.local()


def get_session(proxy_url):
    """Retrieve or create thread-local requests.Session configured with Tor proxy."""
    cur_proxy = getattr(thread_local, "proxy_url", None)
    if hasattr(thread_local, "session") and cur_proxy != proxy_url:
        try:
            thread_local.session.close()
        except Exception:
            pass
        try:
            del thread_local.session
        except Exception:
            pass
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.proxies = {"http": proxy_url, "https": proxy_url}
        s.headers.update(random.choice(HEADERS_LIST))
        thread_local.session = s
        thread_local.proxy_url = proxy_url
    return thread_local.session


def close_all_thread_sessions():
    """Close and clean up thread-local sessions on NEWNYM or shutdown."""
    try:
        if hasattr(thread_local, "session"):
            try:
                thread_local.session.close()
            except Exception:
                pass
            try:
                del thread_local.session
            except Exception:
                pass
        if hasattr(thread_local, "proxy_url"):
            try:
                del thread_local.proxy_url
            except Exception:
                pass
    except Exception:
        pass


class DomainRateLimiter:
    """Thread-safe per-domain rate limiter to avoid overwhelming .onion services."""

    def __init__(self, min_domain_delay=0.7):
        self.min_domain_delay = min_domain_delay
        self.last_domain_request = {}
        self.lock = threading.Lock()

    def wait_for_domain(self, domain):
        """Wait if needed to ensure at least min_domain_delay has passed since last request to domain."""
        if not domain or self.min_domain_delay <= 0:
            return

        with self.lock:
            now = time.time()
            last_time = self.last_domain_request.get(domain, 0)
            wait_time = (last_time + self.min_domain_delay) - now
            if wait_time > 0:
                self.last_domain_request[domain] = now + wait_time
            else:
                self.last_domain_request[domain] = now

        if wait_time > 0:
            time.sleep(min(wait_time, 5.0))

    async def async_wait_for_domain(self, domain):
        """Asynchronously pause if needed for rate limiting without blocking the event loop."""
        if not domain or self.min_domain_delay <= 0:
            return

        with self.lock:
            now = time.time()
            last_time = self.last_domain_request.get(domain, 0)
            wait_time = (last_time + self.min_domain_delay) - now
            if wait_time > 0:
                self.last_domain_request[domain] = now + wait_time
            else:
                self.last_domain_request[domain] = now

        if wait_time > 0:
            await asyncio.sleep(min(wait_time, 5.0))


class RobotsChecker:
    """Optional robots.txt parser and domain policy cache."""

    def __init__(self, enabled=False):
        self.enabled = enabled
        self.cache = {}
        self.lock = threading.Lock()

    def is_allowed(self, url, sess=None, proxy_url=None, allow_clearnet=False):
        if not self.enabled:
            return True
        parsed = urlparse(url)
        domain = parsed.netloc
        if not domain:
            return True

        with self.lock:
            if domain in self.cache:
                rp = self.cache[domain]
                return rp.can_fetch("*", url) if rp else True

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rp = None
        try:
            resp = guarded_get(
                robots_url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=8
            )
            if resp.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
        except Exception:
            rp = None

        with self.lock:
            self.cache[domain] = rp

        return rp.can_fetch("*", url) if rp else True


class SessionManager:
    """Manages thread-local requests sessions for Tor routing."""

    def get_session(self, proxy_url):
        return get_session(proxy_url)

    def close_all(self):
        close_all_thread_sessions()


class OnionFetcher:
    """
    Handles network fetching with retry logic, exponential backoff,
    domain rate-limiting, lxml fast HTML parsing, and optional async execution.
    """

    def __init__(
        self,
        session_manager=None,
        detector=None,
        max_retries=2,
        domain_delay=0.7,
        respect_robots=False,
        seed_manager=None,
        allow_clearnet=False,
    ):
        self._lock = threading.Lock()
        self.session_manager = session_manager or SessionManager()
        self.detector = detector or ContentDetector()
        self.max_retries = max_retries
        self.rate_limiter = DomainRateLimiter(min_domain_delay=domain_delay)
        self.robots_checker = RobotsChecker(enabled=respect_robots)
        self.seed_manager = seed_manager or SeedManager()
        self.allow_clearnet = allow_clearnet

    def set_allow_clearnet(self, value: bool) -> None:
        """Thread-safely update allow_clearnet setting and log security event."""
        with self._lock:
            self.allow_clearnet = bool(value)
        logging.getLogger("onion_search").info(f"[SECURITY] allow_clearnet -> {bool(value)}")

    def fetch_tor66_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from Tor66 directory."""
        return self.seed_manager.fetch_tor66(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_deepsearch_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from Deep Search directory."""
        return self.seed_manager.fetch_deepsearch(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_haystak_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from Haystak search engine."""
        return self.seed_manager.fetch_haystak(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_onionland_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from OnionLand search engine."""
        return self.seed_manager.fetch_onionland(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_torch_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from Torch search engine."""
        return self.seed_manager.fetch_torch(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_notevil_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Set[str]:
        """Fetch discovered .onion addresses from not Evil search engine."""
        return self.seed_manager.fetch_notevil(proxy_url=proxy_url, allow_clearnet=allow_clearnet)

    def fetch_all_seeds(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        selected_sources: Optional[List[str]] = None,
        use_only_healthy: bool = False,
        on_source_progress: Optional[Callable[[str, int], None]] = None,
    ) -> Tuple[Set[str], Dict[str, int]]:
        """Fetch and aggregate seeds from all plugin sources."""
        return self.seed_manager.fetch_all(
            proxy_url=proxy_url,
            allow_clearnet=allow_clearnet,
            selected_sources=selected_sources,
            use_only_healthy=use_only_healthy,
            on_source_progress=on_source_progress,
        )

    def fetch_github_seeds(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> set:
        """
        Fetch discovered .onion addresses from GitHub and Ahmia lists.
        Enforces Tor proxy routing unless clearnet is explicitly enabled via net_guard.
        """
        found = set()
        reg = re.compile(r"[a-z2-7]{56}\.onion")
        for src in GITHUB_SOURCES:
            try:
                r = guarded_get(
                    src,
                    proxy_url=proxy_url,
                    allow_clearnet=allow_clearnet,
                    timeout=15,
                    headers=random.choice(HEADERS_LIST),
                )
                for m in reg.findall(r.text):
                    found.add(f"http://{m}")
            except Exception as e:
                logging.getLogger("onion_search").warning(
                    f"[SECURITY] fetch_github_seeds nem sikerült: {e}"
                )
        try:
            r = guarded_get(
                "https://ahmia.fi/onions/",
                proxy_url=proxy_url,
                allow_clearnet=allow_clearnet,
                timeout=15,
                headers=random.choice(HEADERS_LIST),
            )
            for m in reg.findall(r.text):
                found.add(f"http://{m}")
        except Exception as e:
            logging.getLogger("onion_search").warning(
                f"[SECURITY] fetch_github_seeds ahmia.fi nem sikerült: {e}"
            )
        return found

    def search_ahmia(
        self,
        queries,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        is_running_cb=None,
    ) -> set:
        """
        Query Ahmia search engine for keywords and extract .onion links.
        Prevents deanonymization by routing through Tor proxy unless clearnet is allowed.
        """
        all_onions = set()
        for q in queries:
            if is_running_cb and not is_running_cb():
                break
            try:
                r = guarded_get(
                    f"https://ahmia.fi/search/?q={requests.utils.quote(q)}",
                    proxy_url=proxy_url,
                    allow_clearnet=allow_clearnet,
                    timeout=15,
                    headers=random.choice(HEADERS_LIST),
                )
                soup = BeautifulSoup(r.text, HTML_PARSER)
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    if ".onion" in h:
                        if "redirect_url=" in h:
                            h = h.split("redirect_url=")[1]
                        norm = normalize_onion_url(h)
                        if norm:
                            all_onions.add(norm)
            except Exception as e:
                logging.getLogger("onion_search").warning(
                    f"[SECURITY] search_ahmia lekérdezés nem sikerült: {e}"
                )
        return all_onions

    def search_onionsearchengine(
        self,
        queries,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        is_running_cb=None,
    ) -> set:
        """Query OnionSearchEngine for keywords and extract .onion links."""
        all_onions = set()
        for q in queries:
            if is_running_cb and not is_running_cb():
                break
            try:
                r = guarded_get(
                    f"https://onionsearchengine.com/search.php?search={requests.utils.quote(q)}",
                    proxy_url=proxy_url,
                    allow_clearnet=allow_clearnet,
                    timeout=15,
                    headers=random.choice(HEADERS_LIST),
                )
                soup = BeautifulSoup(r.text, HTML_PARSER)
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    if ".onion" in h:
                        norm = normalize_onion_url(h)
                        if norm:
                            all_onions.add(norm)
            except Exception as e:
                logging.getLogger("onion_search").warning(
                    f"[SECURITY] search_onionsearchengine lekérdezés nem sikerült: {e}"
                )
        return all_onions

    def parse_html_content(self, html, final_url, url, now_ts):
        """Fast HTML parsing and feature extraction using lxml and fingerprint caching."""
        soup = BeautifulSoup(html, HTML_PARSER)
        html_lang = soup.html.get("lang", "") if soup.html else ""

        title_tmp = (
            soup.title.string.strip()[:70]
            if soup.title and soup.title.string
            else "Nincs cím"
        )

        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        text = re.sub(r"\s+", " ", soup.get_text()).lower().strip()[:8000]

        if len(text) < 200:
            return {
                "url": final_url,
                "status": "empty",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        fp = self.detector.extract_fingerprint(text)
        btc = self.detector.extract_bitcoin_addresses(text)

        # High-performance classification with fingerprint caching
        lang, category = self.detector.classify_with_cache(
            fp=fp, title=title_tmp, text=text, html_lang=html_lang, soup=soup
        )

        return {
            "url": final_url,
            "status": "ok",
            "title": title_tmp,
            "text": text,
            "snippet": text[:120],
            "fp": fp,
            "btc": btc,
            "ts": now_ts,
            "lang": lang,
            "category": category,
        }

    def fetch_page(self, url, proxy_url, is_running_cb=None):
        """
        Synchronous fetch with domain rate limiting, retry logic, and lxml parsing.
        """
        with self._lock:
            allow_clearnet = self.allow_clearnet

        now_ts = time.time()
        domain = urlparse(url).netloc

        if not is_proxy_allowed(proxy_url, allow_clearnet):
            return {
                "url": url,
                "status": "filtered",
                "reason": "Clearnet access disallowed without Tor proxy",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        if not self.robots_checker.is_allowed(
            url, proxy_url=proxy_url, allow_clearnet=allow_clearnet
        ):
            return {
                "url": url,
                "status": "filtered",
                "reason": "robots.txt disallowed",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        last_error = None
        last_code = None
        final_url = url
        html = None

        for attempt in range(self.max_retries + 1):
            if is_running_cb and not is_running_cb():
                return {
                    "url": url,
                    "status": "canceled",
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }

            self.rate_limiter.wait_for_domain(domain)

            try:
                headers = random.choice(HEADERS_LIST)
                cur_url = url
                max_redirects = 5
                redirect_count = 0
                r = None

                while redirect_count <= max_redirects:
                    r = guarded_get(
                        cur_url,
                        proxy_url=proxy_url,
                        allow_clearnet=allow_clearnet,
                        timeout=TIMEOUT_GET,
                        allow_redirects=False,
                        headers=headers,
                        stream=True,
                    )

                    if r.status_code in (301, 302, 303, 307, 308) and "Location" in r.headers:
                        raw_loc = r.headers["Location"]
                        next_url = urllib.parse.urljoin(cur_url, raw_loc)

                        if not allow_clearnet and not is_onion_host(next_url):
                            r.close()
                            return {
                                "url": next_url,
                                "status": "filtered",
                                "reason": "redirect to clearnet disallowed",
                                "ts": now_ts,
                                "lang": "en",
                                "category": "other",
                            }
                        cur_url = next_url
                        redirect_count += 1
                        r.close()
                    else:
                        break

                final_url = cur_url
                last_code = r.status_code

                if r.status_code in (429, 503) and attempt < self.max_retries:
                    r.close()
                    backoff = (2**attempt) * 1.5
                    time.sleep(backoff)
                    continue

                if r.status_code != 200:
                    r.close()
                    if r.status_code in (500, 502, 504) and attempt < self.max_retries:
                        backoff = 2**attempt
                        time.sleep(backoff)
                        continue

                    return {
                        "url": final_url if is_onion_host(final_url) else url,
                        "status": "dead",
                        "code": r.status_code,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

                chunks = []
                downloaded = 0
                too_large = False
                for chunk in r.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > MAX_RESPONSE_BYTES:
                        too_large = True
                        break
                    chunks.append(chunk)

                r.close()

                if too_large:
                    return {
                        "url": final_url if is_onion_host(final_url) else url,
                        "status": "dead",
                        "err": "too_large",
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

                raw_bytes = b"".join(chunks)
                if len(raw_bytes) < 300:
                    return {
                        "url": final_url if is_onion_host(final_url) else url,
                        "status": "dead",
                        "code": r.status_code,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

                encoding = r.encoding or "utf-8"
                try:
                    html = raw_bytes.decode(encoding, errors="replace")
                except Exception:
                    html = raw_bytes.decode("utf-8", errors="replace")
                break

            except TorOnlyViolation:
                return {
                    "url": url,
                    "status": "filtered",
                    "reason": "TorOnlyViolation",
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                Exception,
            ) as e:
                last_error = str(e)[:100]
                if attempt < self.max_retries:
                    backoff = 2**attempt
                    time.sleep(backoff)
                    continue
                else:
                    return {
                        "url": url,
                        "status": "dead",
                        "err": last_error,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

        if html is None:
            return {
                "url": url,
                "status": "dead",
                "err": last_error or f"HTTP {last_code}",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        url_to_save = final_url if is_onion_host(final_url) else url
        return self.parse_html_content(html, url_to_save, url, now_ts)

    async def async_fetch_page_httpx(self, client, url, is_running_cb=None, proxy_url=None):
        """
        Asynchronous fetch using httpx.AsyncClient with SOCKS5h Tor proxy support,
        retry logic, rate limiting, and lxml HTML parsing.
        """
        with self._lock:
            allow_clearnet = self.allow_clearnet

        now_ts = time.time()
        domain = urlparse(url).netloc

        if not is_proxy_allowed(proxy_url, allow_clearnet):
            return {
                "url": url,
                "status": "filtered",
                "reason": "Clearnet access disallowed without Tor proxy",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        allowed = await asyncio.to_thread(
            self.robots_checker.is_allowed,
            url,
            None,
            proxy_url=proxy_url,
            allow_clearnet=allow_clearnet,
        )
        if not allowed:
            return {
                "url": url,
                "status": "filtered",
                "reason": "robots.txt disallowed",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        last_error = None
        last_code = None
        final_url = url
        html = None

        for attempt in range(self.max_retries + 1):
            if is_running_cb and not is_running_cb():
                return {
                    "url": url,
                    "status": "canceled",
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }

            await self.rate_limiter.async_wait_for_domain(domain)

            headers = random.choice(HEADERS_LIST)
            retry_delay = None
            try:
                cur_url = url
                max_redirects = 5
                redirect_count = 0
                too_large = False

                while redirect_count <= max_redirects:
                    stream_cm = client.stream("GET", cur_url, headers=headers, follow_redirects=False)
                    async with stream_cm as r:
                        last_code = getattr(r, "status_code", 200)
                        location_val = None
                        if hasattr(r, "headers") and r.headers:
                            for k, v in r.headers.items():
                                if k.lower() == "location":
                                    location_val = v
                                    break

                        if last_code in (301, 302, 303, 307, 308) and location_val:
                            next_url = urllib.parse.urljoin(cur_url, location_val)

                            if not allow_clearnet and not is_onion_host(next_url):
                                return {
                                    "url": next_url,
                                    "status": "filtered",
                                    "reason": "redirect to clearnet disallowed",
                                    "ts": now_ts,
                                    "lang": "en",
                                    "category": "other",
                                }
                            cur_url = next_url
                            redirect_count += 1
                            continue

                        final_url = str(getattr(r, "url", cur_url))
                        if last_code in (429, 503) and attempt < self.max_retries:
                            retry_delay = (2**attempt) * 1.5
                            break

                        if last_code in (500, 502, 504) and attempt < self.max_retries:
                            retry_delay = 2**attempt
                            break

                        if last_code != 200:
                            return {
                                "url": final_url if is_onion_host(final_url) else url,
                                "status": "dead",
                                "code": last_code,
                                "ts": now_ts,
                                "lang": "en",
                                "category": "other",
                            }

                        chunks = []
                        downloaded = 0
                        async for chunk in r.aiter_bytes():
                            downloaded += len(chunk)
                            if downloaded > MAX_RESPONSE_BYTES:
                                too_large = True
                                break
                            chunks.append(chunk)

                        if too_large:
                            return {
                                "url": final_url if is_onion_host(final_url) else url,
                                "status": "dead",
                                "err": "too_large",
                                "ts": now_ts,
                                "lang": "en",
                                "category": "other",
                            }

                        raw_bytes = b"".join(chunks)
                        if len(raw_bytes) < 300:
                            return {
                                "url": final_url if is_onion_host(final_url) else url,
                                "status": "dead",
                                "code": last_code,
                                "ts": now_ts,
                                "lang": "en",
                                "category": "other",
                            }

                        html = raw_bytes.decode("utf-8", errors="replace")
                        break

                if retry_delay is not None:
                    await asyncio.sleep(retry_delay)
                    continue

                if html is not None:
                    break

            except Exception as e:
                last_error = str(e)[:100]
                if attempt < self.max_retries:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return {
                        "url": url,
                        "status": "dead",
                        "err": last_error,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

        if html is None:
            return {
                "url": url,
                "status": "dead",
                "err": last_error or f"HTTP {last_code}",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        url_to_save = final_url if is_onion_host(final_url) else url
        return self.parse_html_content(html, url_to_save, url, now_ts)

    def fetch_url(
        self,
        url: str,
        proxy_url: Optional[str] = None,
        is_running_cb: Optional[Callable[[], bool]] = None,
        async_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Dual-mode fetch entry point.
        Uses synchronous requests if async_mode is False.
        Uses httpx/asyncio if async_mode is True, falling back to sync on missing dependencies or error.
        """
        with self._lock:
            allow_clearnet = self.allow_clearnet

        if not is_proxy_allowed(proxy_url, allow_clearnet):
            return {
                "url": url,
                "status": "filtered",
                "reason": "Clearnet access disallowed without Tor proxy",
                "ts": time.time(),
                "lang": "en",
                "category": "other",
            }

        if not async_mode:
            return self.fetch_page(url, proxy_url, is_running_cb=is_running_cb)

        if not HTTPX_AVAILABLE:
            logging.getLogger("onion_search").warning(
                "[ASYNC MODE] 'httpx' csomag nem elérhető. Visszaállás szinkron módra."
            )
            return self.fetch_page(url, proxy_url, is_running_cb=is_running_cb)

        try:
            async def _run_async():
                transport_kwargs = {}
                if proxy_url:
                    transport_kwargs["proxy"] = proxy_url
                async with httpx.AsyncClient(timeout=TIMEOUT_GET, follow_redirects=True, **transport_kwargs) as client:
                    return await self.async_fetch_page_httpx(client, url, is_running_cb=is_running_cb, proxy_url=proxy_url)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_run_async(), loop)
                return future.result()
            else:
                return asyncio.run(_run_async())
        except Exception as e:
            logging.getLogger("onion_search").warning(
                f"[ASYNC MODE HIBA] {e}. Visszaállás szinkron módra."
            )
            return self.fetch_page(url, proxy_url, is_running_cb=is_running_cb)

    async def async_fetch_page(self, client, url, is_running_cb=None):
        """
        Asynchronous fetch using shared aiohttp.ClientSession connection pool.
        Eliminates per-thread socket opening, achieving 10-50x concurrency efficiency.
        """
        now_ts = time.time()
        domain = urlparse(url).netloc

        if not self.robots_checker.is_allowed(url, None):
            return {
                "url": url,
                "status": "filtered",
                "reason": "robots.txt disallowed",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        last_error = None
        last_code = None
        final_url = url
        html = None

        for attempt in range(self.max_retries + 1):
            if is_running_cb and not is_running_cb():
                return {
                    "url": url,
                    "status": "canceled",
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }

            await self.rate_limiter.async_wait_for_domain(domain)

            headers = random.choice(HEADERS_LIST)
            try:
                res_cm = client.get(url, timeout=TIMEOUT_GET, allow_redirects=True, headers=headers)
                if hasattr(res_cm, "__aenter__"):
                    async with res_cm as r:
                        final_url = str(getattr(r, "url", url))
                        status_val = getattr(r, "status", None)
                        if status_val is None or not isinstance(status_val, int):
                            status_val = getattr(r, "status_code", 200)
                            if not isinstance(status_val, int):
                                status_val = 200
                        last_code = status_val
                        text_attr = getattr(r, "text", "")
                        if asyncio.iscoroutine(text_attr):
                            text = await text_attr
                        elif callable(text_attr):
                            res_t = text_attr()
                            text = await res_t if asyncio.iscoroutine(res_t) else str(res_t)
                        else:
                            text = str(text_attr)
                elif asyncio.iscoroutine(res_cm):
                    r = await res_cm
                    final_url = str(getattr(r, "url", url))
                    status_val = getattr(r, "status", None)
                    if status_val is None or not isinstance(status_val, int):
                        status_val = getattr(r, "status_code", 200)
                        if not isinstance(status_val, int):
                            status_val = 200
                    last_code = status_val
                    text_attr = getattr(r, "text", "")
                    if asyncio.iscoroutine(text_attr):
                        text = await text_attr
                    elif callable(text_attr):
                        res_t = text_attr()
                        text = await res_t if asyncio.iscoroutine(res_t) else str(res_t)
                    else:
                        text = str(text_attr)
                else:
                    r = res_cm
                    final_url = str(getattr(r, "url", url))
                    status_val = getattr(r, "status", None)
                    if status_val is None or not isinstance(status_val, int):
                        status_val = getattr(r, "status_code", 200)
                        if not isinstance(status_val, int):
                            status_val = 200
                    last_code = status_val
                    text_attr = getattr(r, "text", "")
                    if asyncio.iscoroutine(text_attr):
                        text = await text_attr
                    elif callable(text_attr):
                        res_t = text_attr()
                        text = await res_t if asyncio.iscoroutine(res_t) else str(res_t)
                    else:
                        text = str(text_attr)

                if last_code in (429, 503) and attempt < self.max_retries:
                    backoff = (2**attempt) * 1.5
                    await asyncio.sleep(backoff)
                    continue

                if last_code != 200 or len(text) < 300:
                    if last_code in (500, 502, 504) and attempt < self.max_retries:
                        backoff = 2**attempt
                        await asyncio.sleep(backoff)
                        continue

                    return {
                        "url": final_url if is_onion_host(final_url) else url,
                        "status": "dead",
                        "code": last_code,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

                html = text
                break

            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                last_error = str(e)[:100]
                if attempt < self.max_retries:
                    backoff = 2**attempt
                    await asyncio.sleep(backoff)
                    continue
                else:
                    return {
                        "url": url,
                        "status": "dead",
                        "err": last_error,
                        "ts": now_ts,
                        "lang": "en",
                        "category": "other",
                    }

        if html is None:
            return {
                "url": url,
                "status": "dead",
                "err": last_error or f"HTTP {last_code}",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        url_to_save = final_url if is_onion_host(final_url) else url
        return self.parse_html_content(html, url_to_save, url, now_ts)

