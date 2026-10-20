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
Comprehensive tests for Tor-only network guard enforcement, SOCKS5h validation,
response byte limits, redirect safety filtering, and static code compliance.
"""
import ast
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from onion_search.config import MAX_RESPONSE_BYTES
from onion_search.core.fetcher import OnionFetcher
from onion_search.utils.net_guard import TorOnlyViolation, guarded_get, is_proxy_allowed


class DummyStreamResponse:
    """Mock streaming HTTP response for requests and httpx testing."""

    def __init__(self, status_code=200, headers=None, content_chunks=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content_chunks = content_chunks or [b"<html><head><title>Test</title></head><body>" + b"Hello " * 100 + b"</body></html>"]
        self.encoding = "utf-8"
        self.url = "http://testonion1234567890abcdef.onion"

    def iter_content(self, chunk_size=8192):
        for c in self.content_chunks:
            yield c

    def close(self):
        pass


def test_no_outbound_network_without_proxy_and_clearnet_false():
    """a) Verify no network calls occur without proxy when allow_clearnet is False."""
    fetcher = OnionFetcher(allow_clearnet=False)

    with patch("requests.get") as mock_req:
        # search_onionsearchengine
        res_ose = fetcher.search_onionsearchengine(["test"], proxy_url=None, allow_clearnet=False)
        assert res_ose == set()

        # search_ahmia
        res_ahmia = fetcher.search_ahmia(["test"], proxy_url=None, allow_clearnet=False)
        assert res_ahmia == set()

        # fetch_github_seeds
        res_gh = fetcher.fetch_github_seeds(proxy_url=None, allow_clearnet=False)
        assert res_gh == set()

        # fetch_page
        res_page = fetcher.fetch_page("http://example.onion", proxy_url=None)
        assert res_page["status"] == "filtered"

        # fetch_url
        res_url = fetcher.fetch_url("http://example.onion", proxy_url=None, async_mode=False)
        assert res_url["status"] == "filtered"

        # Confirm requests.request was never invoked
        mock_req.assert_not_called()


def test_socks5_proxy_without_h_rejected():
    """b) Verify proxy URLs with socks5:// (lacking 'h') are rejected to prevent DNS leaks."""
    fetcher = OnionFetcher(allow_clearnet=False)

    with pytest.raises(TorOnlyViolation) as exc_info:
        guarded_get("http://example.onion", proxy_url="socks5://127.0.0.1:9050", allow_clearnet=False)
    assert "socks5h://" in str(exc_info.value)

    res = fetcher.fetch_page("http://example.onion", proxy_url="socks5://127.0.0.1:9050")
    assert res["status"] == "filtered"


def test_allow_clearnet_true_allows_request():
    """c) Verify allow_clearnet=True allows requests to run without proxy."""
    mock_resp = DummyStreamResponse(status_code=200)
    with patch("requests.get", return_value=mock_resp) as mock_req:
        res = guarded_get("https://ahmia.fi/", proxy_url=None, allow_clearnet=True)
        assert res.status_code == 200
        mock_req.assert_called_once()


def test_too_large_response_handling():
    """d) Verify responses exceeding MAX_RESPONSE_BYTES receive 'too_large' status."""
    fetcher = OnionFetcher(allow_clearnet=True)
    big_chunk = b"A" * (MAX_RESPONSE_BYTES + 1024)
    mock_resp = DummyStreamResponse(status_code=200, content_chunks=[big_chunk])

    with patch("requests.get", return_value=mock_resp):
        res = fetcher.fetch_page("http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")
        assert res["status"] == "dead"
        assert res.get("err") == "too_large"


def test_non_onion_redirect_filtered():
    """e) Verify non-.onion redirect under allow_clearnet=False returns 'filtered' status."""
    fetcher = OnionFetcher(allow_clearnet=False)
    redirect_resp = DummyStreamResponse(
        status_code=302, headers={"Location": "https://clearnet-site.com/login"}
    )

    with patch("requests.get", return_value=redirect_resp):
        res = fetcher.fetch_page("http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")
        assert res["status"] == "filtered"
        assert "clearnet disallowed" in res.get("reason", "")


def test_static_source_code_guard_compliance():
    """
    f) Static source code analysis of onion_search/ searching for direct calls to
    requests.get, requests.head, or requests.post, ensuring net_guard.py is the sole
    module where outbound requests calls are created (exempting neonym.py's check_tor_socks / probe_tor_socks_port).
    """
    repo_root = Path(__file__).resolve().parent.parent / "onion_search"
    violations = []

    exempt_files = {"net_guard.py", "neonym.py"}

    for py_file in repo_root.rglob("*.py"):
        if py_file.name in exempt_files:
            continue

        code = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(code, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Check requests.get / requests.head / requests.post
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.value.id == "requests" and func.attr in ("get", "head", "post"):
                        violations.append(f"{py_file.relative_to(repo_root)}:{node.lineno} -> direct requests.{func.attr}() call")

    assert not violations, f"Found direct requests call outside net_guard.py: {violations}"
