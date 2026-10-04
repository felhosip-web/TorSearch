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
Core domain logic module.
Developed by HES Projects by FePe.
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
