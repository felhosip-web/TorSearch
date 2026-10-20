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
Central network security guard for Onion Kereső.
Enforces strict Tor-only routing policies, SOCKS5h proxy scheme checking to prevent DNS leaks,
and logs security violations with sanitized URLs.
Developed by HES Projects by FePe.
"""
import logging
from typing import Optional
import requests

logger = logging.getLogger("onion_search")


class TorOnlyViolation(Exception):
    """Raised when an outgoing network request violates Tor-only security requirements."""
    pass


def is_proxy_allowed(proxy_url: Optional[str], allow_clearnet: bool = False) -> bool:
    """
    Check whether network access is permitted under the current configuration.
    Returns True if allow_clearnet is True or a valid socks5h:// proxy_url is configured.
    """
    if allow_clearnet:
        return True
    if proxy_url and isinstance(proxy_url, str) and proxy_url.startswith("socks5h://"):
        return True
    return False


def _sanitize_url(url: str) -> str:
    """Sanitize URL by removing query parameters for safe logging."""
    if not url:
        return ""
    return url.split("?")[0]


def _check_guard_policy(url: str, proxy_url: Optional[str] = None, allow_clearnet: bool = False):
    safe_url = _sanitize_url(url)

    if not allow_clearnet and not proxy_url:
        logger.warning(
            f"[SECURITY] Közvetlen hálózati kérés blokkolva Tor proxy nélkül! URL: {safe_url}"
        )
        raise TorOnlyViolation(f"Clearnet kérés tiltva Tor proxy nélkül: {safe_url}")

    if proxy_url:
        if not proxy_url.startswith("socks5h://"):
            logger.warning(
                f"[SECURITY] Nem biztonságos proxy séma visszautasítva (socks5h:// kötelező a DNS-szivárgás ellen): {proxy_url}"
            )
            raise TorOnlyViolation(
                f"A proxy-nak socks5h://-val kell kezdődnie (DNS szivárgás megelőzése): {proxy_url}"
            )


def guarded_get(
    url: str,
    proxy_url: Optional[str] = None,
    allow_clearnet: bool = False,
    stream: bool = False,
    **kwargs
) -> requests.Response:
    """Execute a guarded GET request using requests.get enforcing Tor-only proxy safety rules."""
    _check_guard_policy(url, proxy_url=proxy_url, allow_clearnet=allow_clearnet)
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    return requests.get(url, proxies=proxies, stream=stream, **kwargs)


def guarded_head(
    url: str,
    proxy_url: Optional[str] = None,
    allow_clearnet: bool = False,
    **kwargs
) -> requests.Response:
    """Execute a guarded HEAD request using requests.head enforcing Tor-only proxy safety rules."""
    _check_guard_policy(url, proxy_url=proxy_url, allow_clearnet=allow_clearnet)
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    return requests.head(url, proxies=proxies, **kwargs)


def guarded_request(
    url: str,
    proxy_url: Optional[str] = None,
    allow_clearnet: bool = False,
    method: str = "GET",
    stream: bool = False,
    **kwargs
) -> requests.Response:
    """Execute an HTTP request enforcing Tor-only proxy safety rules."""
    if method.upper() == "HEAD":
        return guarded_head(url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, **kwargs)
    return guarded_get(url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, stream=stream, **kwargs)
