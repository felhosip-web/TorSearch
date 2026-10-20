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
Unit tests for Dual-Mode Network Fetcher (Sync / Async) and configuration switch.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from onion_search.config import AppConfig, ConfigManager
from onion_search.core.fetcher import OnionFetcher, DomainRateLimiter


class MockResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text
        self.url = "http://testonion1234567890abcdef.onion"


def test_appconfig_async_mode_default():
    """Verify AppConfig defaults async_mode to False."""
    cfg = AppConfig()
    assert cfg.async_mode is False


def test_appconfig_async_mode_serialization(tmp_path):
    """Verify serialization and deserialization of async_mode in ConfigManager."""
    cfg_file = tmp_path / "config.json"
    cm = ConfigManager(config_file=cfg_file)
    cfg = cm.load()
    assert cfg.async_mode is False

    cfg.async_mode = True
    cm.save(cfg)

    loaded_cfg = cm.load()
    assert loaded_cfg.async_mode is True


def test_fetch_url_dispatches_sync(monkeypatch):
    """Verify fetch_url calls fetch_page when async_mode is False."""
    fetcher = OnionFetcher()
    mock_fetch_page = MagicMock(return_value={"status": "ok", "title": "Sync Title"})
    monkeypatch.setattr(fetcher, "fetch_page", mock_fetch_page)

    res = fetcher.fetch_url("http://example.onion", "socks5h://127.0.0.1:9050", async_mode=False)

    assert res["status"] == "ok"
    assert res["title"] == "Sync Title"
    mock_fetch_page.assert_called_once_with(
        "http://example.onion", "socks5h://127.0.0.1:9050", is_running_cb=None
    )


def test_fetch_url_fallback_on_httpx_missing(monkeypatch):
    """Verify fetch_url falls back to fetch_page when httpx is unavailable."""
    fetcher = OnionFetcher()
    mock_fetch_page = MagicMock(return_value={"status": "ok", "title": "Fallback Sync"})
    monkeypatch.setattr(fetcher, "fetch_page", mock_fetch_page)
    monkeypatch.setattr("onion_search.core.fetcher.HTTPX_AVAILABLE", False)

    res = fetcher.fetch_url("http://example.onion", "socks5h://127.0.0.1:9050", async_mode=True)

    assert res["status"] == "ok"
    assert res["title"] == "Fallback Sync"
    mock_fetch_page.assert_called_once()


def test_fetch_url_fallback_on_async_exception(monkeypatch):
    """Verify fetch_url falls back to fetch_page when async_mode execution raises an exception."""
    fetcher = OnionFetcher()
    mock_fetch_page = MagicMock(return_value={"status": "ok", "title": "Exception Fallback"})
    monkeypatch.setattr(fetcher, "fetch_page", mock_fetch_page)
    monkeypatch.setattr("onion_search.core.fetcher.HTTPX_AVAILABLE", True)
    monkeypatch.setattr(fetcher, "async_fetch_page_httpx", MagicMock(side_effect=RuntimeError("HTTPX Error")))

    res = fetcher.fetch_url("http://example.onion", "socks5h://127.0.0.1:9050", async_mode=True)

    assert res["status"] == "ok"
    assert res["title"] == "Exception Fallback"
    mock_fetch_page.assert_called_once()


def test_async_fetch_page_httpx_success():
    """Verify async_fetch_page_httpx successfully fetches and parses page content."""
    fetcher = OnionFetcher()

    sample_html = b"<html><head><title>Test Onion Page</title></head><body>" + b"Content for testing onion page " * 20 + b"</body></html>"

    class AsyncChunkStream:
        def __init__(self, chunks, status_code=200):
            self.status_code = status_code
            self.headers = {}
            self.url = "http://testonion1234567890abcdef.onion"
            self._chunks = chunks

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_bytes(self):
            for c in self._chunks:
                yield c

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=AsyncChunkStream([sample_html], status_code=200))

    async def _test():
        return await fetcher.async_fetch_page_httpx(mock_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")

    res = asyncio.run(_test())

    assert res["status"] == "ok"
    assert res["title"] == "Test Onion Page"


def test_async_fetch_page_httpx_dead_link():
    """Verify async_fetch_page_httpx handles HTTP 404 / dead link appropriately."""
    fetcher = OnionFetcher(max_retries=0)

    class AsyncChunkStream404:
        def __init__(self):
            self.status_code = 404
            self.headers = {}
            self.url = "http://testonion1234567890abcdef.onion"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def aiter_bytes(self):
            yield b"Not Found"

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=AsyncChunkStream404())

    async def _test():
        return await fetcher.async_fetch_page_httpx(mock_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")

    res = asyncio.run(_test())

    assert res["status"] == "dead"
    assert res["code"] == 404


def test_async_domain_rate_limiter():
    """Verify DomainRateLimiter async_wait_for_domain pauses as expected."""
    limiter = DomainRateLimiter(min_domain_delay=0.1)

    async def _test():
        start = asyncio.get_event_loop().time()
        await limiter.async_wait_for_domain("example.onion")
        await limiter.async_wait_for_domain("example.onion")
        end = asyncio.get_event_loop().time()
        return end - start

    elapsed = asyncio.run(_test())
    assert elapsed >= 0.08


def test_shared_sync_and_async_rate_limiter():
    """Verify sync wait_for_domain and async async_wait_for_domain share state consistently."""
    limiter = DomainRateLimiter(min_domain_delay=0.1)

    limiter.wait_for_domain("testdomain.onion")
    # Immediate second call in async mode should detect last request time
    async def _test():
        start = asyncio.get_event_loop().time()
        await limiter.async_wait_for_domain("testdomain.onion")
        end = asyncio.get_event_loop().time()
        return end - start

    elapsed = asyncio.run(_test())
    assert elapsed >= 0.05


def test_socks5h_proxy_preservation(monkeypatch):
    """Verify fetch_url preserves socks5h:// URL format for Tor DNS resolution."""
    fetcher = OnionFetcher()
    monkeypatch.setattr("onion_search.core.fetcher.HTTPX_AVAILABLE", True)

    captured_kwargs = {}

    class MockAsyncClient:
        def __init__(self, **kwargs):
            nonlocal captured_kwargs
            captured_kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
    monkeypatch.setattr(fetcher, "async_fetch_page_httpx", AsyncMock(return_value={"status": "ok"}))

    res = fetcher.fetch_url("http://example.onion", "socks5h://127.0.0.1:9050", async_mode=True)

    assert res["status"] == "ok"
    assert captured_kwargs.get("proxy") == "socks5h://127.0.0.1:9050"
