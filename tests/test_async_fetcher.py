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
from tests.fakes import FakeAsyncClient, FakeStreamResponse


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
    fake_client = FakeAsyncClient(FakeStreamResponse(status_code=200))

    async def _test():
        return await fetcher.async_fetch_page_httpx(fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")

    res = asyncio.run(_test())

    assert res["status"] == "ok"
    assert res["title"] == "Test Onion Page"


def test_async_fetch_page_httpx_dead_link():
    """Verify async_fetch_page_httpx handles HTTP 404 / dead link appropriately."""
    fetcher = OnionFetcher(max_retries=0)
    fake_client = FakeAsyncClient(FakeStreamResponse(status_code=404, content_chunks=[b"Not Found"]))

    async def _test():
        return await fetcher.async_fetch_page_httpx(fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050")

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


def test_async_fetch_429_backoff_retry():
    """a) Verify 429 then 200 response triggers asyncio.sleep((2**0)*1.5) = 1.5s and parses successfully."""
    fetcher = OnionFetcher(max_retries=2, domain_delay=0.0)
    fake_client = FakeAsyncClient([
        FakeStreamResponse(status_code=429),
        FakeStreamResponse(status_code=200),
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = asyncio.run(fetcher.async_fetch_page_httpx(
            fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050"
        ))

        assert res["status"] == "ok"
        mock_sleep.assert_called_once_with(1.5)


def test_async_fetch_502_backoff_retry():
    """b) Verify 502 -> 502 -> 200 response triggers backoff sleeps (1.0s and 2.0s) and parses successfully."""
    fetcher = OnionFetcher(max_retries=2, domain_delay=0.0)
    fake_client = FakeAsyncClient([
        FakeStreamResponse(status_code=502),
        FakeStreamResponse(status_code=502),
        FakeStreamResponse(status_code=200),
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = asyncio.run(fetcher.async_fetch_page_httpx(
            fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050"
        ))

        assert res["status"] == "ok"
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list == [
            ((1.0,), {}),
            ((2.0,), {}),
        ]


def test_async_fetch_persistent_503_exhaustion():
    """c) Verify persistent 503 error exhausts max_retries, returning 'dead' status and code 503."""
    fetcher = OnionFetcher(max_retries=2, domain_delay=0.0)
    fake_client = FakeAsyncClient([
        FakeStreamResponse(status_code=503),
        FakeStreamResponse(status_code=503),
        FakeStreamResponse(status_code=503),
    ])

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = asyncio.run(fetcher.async_fetch_page_httpx(
            fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050"
        ))

        assert res["status"] == "dead"
        assert res.get("code") == 503
        assert mock_sleep.call_count == 2


def test_async_fetch_non_blocking_robots_check():
    """d) Verify respect_robots=True executes RobotsChecker.is_allowed via asyncio.to_thread without blocking event loop."""
    import time
    fetcher = OnionFetcher(respect_robots=True)
    fake_client = FakeAsyncClient(FakeStreamResponse(status_code=200))

    def _blocking_is_allowed(url, sess=None, proxy_url=None, allow_clearnet=False):
        time.sleep(0.3)
        return True

    ticker_ticks = 0

    async def _ticker():
        nonlocal ticker_ticks
        for _ in range(5):
            await asyncio.sleep(0.05)
            ticker_ticks += 1

    async def _test():
        with patch.object(fetcher.robots_checker, "is_allowed", side_effect=_blocking_is_allowed):
            fetch_task = asyncio.create_task(fetcher.async_fetch_page_httpx(
                fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050"
            ))
            ticker_task = asyncio.create_task(_ticker())
            res, _ = await asyncio.gather(fetch_task, ticker_task)
            return res

    res = asyncio.run(_test())
    assert res["status"] == "ok"
    assert ticker_ticks >= 3  # Proves event loop continued running concurrently!


def test_async_fetch_redirect_filtering():
    """e) Verify redirect to onion.example.com under allow_clearnet=False returns 'filtered' without sending second request."""
    fetcher = OnionFetcher(allow_clearnet=False)
    redirect_resp = FakeStreamResponse(status_code=302, headers={"Location": "http://onion.example.com/login"})
    fake_client = FakeAsyncClient([redirect_resp])

    async def _test():
        return await fetcher.async_fetch_page_httpx(
            fake_client, "http://testonion1234567890abcdef.onion", proxy_url="socks5h://127.0.0.1:9050"
        )

    res = asyncio.run(_test())
    assert res["status"] == "filtered"
    assert "redirect to clearnet disallowed" in res.get("reason", "")
    assert len(fake_client.calls) == 1  # No second request sent!
