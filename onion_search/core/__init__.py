"""
Core domain logic module.
"""
from onion_search.core.detector import (
    ContentDetector,
    detect_language,
    detect_category,
    extract_fingerprint,
    extract_bitcoin_addresses,
)
from onion_search.core.fetcher import (
    OnionFetcher,
    SessionManager,
    get_session,
    close_all_thread_sessions,
)
from onion_search.core.neonym import (
    TorController,
    find_tor_cookie,
    send_newnym_via_control,
    check_tor_socks,
    check_control_port,
)
from onion_search.core.seeds import (
    SeedManager,
    extract_onion_urls,
)

__all__ = [
    "ContentDetector",
    "detect_language",
    "detect_category",
    "extract_fingerprint",
    "extract_bitcoin_addresses",
    "OnionFetcher",
    "SessionManager",
    "get_session",
    "close_all_thread_sessions",
    "TorController",
    "find_tor_cookie",
    "send_newnym_via_control",
    "check_tor_socks",
    "check_control_port",
    "SeedManager",
    "extract_onion_urls",
]
