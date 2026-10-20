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
Unit tests for PerformanceMetrics and PerformanceBenchmarkRunner components.
Developed by HES Projects by FePe.
"""
import time
from unittest.mock import MagicMock, patch

import pytest

from onion_search.ui.benchmark_dialog import PerformanceBenchmarkRunner
from onion_search.ui.main_window import PerformanceMetrics


def test_performance_metrics_recording_and_pruning():
    metrics = PerformanceMetrics(window_seconds=1.0)

    # Initially empty
    stats = metrics.get_stats()
    assert stats["req_per_sec"] == 0.0
    assert stats["avg_latency_ms"] == 0.0
    assert stats["count_in_window"] == 0

    # Record requests
    metrics.record_request(100.0, "unique")
    metrics.record_request(200.0, "unique")

    stats = metrics.get_stats()
    assert stats["count_in_window"] == 2
    assert stats["avg_latency_ms"] == 150.0
    assert stats["req_per_sec"] == 2.0

    # Wait for window to expire
    time.sleep(1.1)
    stats = metrics.get_stats()
    assert stats["count_in_window"] == 0
    assert stats["req_per_sec"] == 0.0


def test_performance_metrics_clear():
    metrics = PerformanceMetrics(window_seconds=10.0)
    metrics.record_request(50.0, "ok")
    assert metrics.get_stats()["count_in_window"] == 1

    metrics.clear()
    assert metrics.get_stats()["count_in_window"] == 0


def test_benchmark_runner_sync():
    mock_fetcher = MagicMock()
    mock_fetcher.fetch_page.return_value = {"status": "unique", "title": "Test"}

    runner = PerformanceBenchmarkRunner(fetcher=mock_fetcher)
    urls = ["http://test1.onion", "http://test2.onion"]

    progress_called = []
    def _prog(curr, tot, msg):
        progress_called.append((curr, tot, msg))

    res = runner.run_sync_benchmark(urls, proxy_url="", workers=2, progress_cb=_prog)

    assert res["mode"] == "Sync"
    assert res["total_requests"] == 2
    assert res["success_count"] == 2
    assert res["fail_count"] == 0
    assert len(progress_called) == 2
    assert mock_fetcher.fetch_page.call_count == 2


def test_benchmark_runner_async():
    mock_fetcher = MagicMock()

    async def _mock_async_fetch(client, url, is_running_cb=None):
        return {"status": "unique", "title": "Test Async"}

    mock_fetcher.async_fetch_page_httpx = _mock_async_fetch

    runner = PerformanceBenchmarkRunner(fetcher=mock_fetcher)
    urls = ["http://async1.onion", "http://async2.onion"]

    progress_called = []
    def _prog(curr, tot, msg):
        progress_called.append((curr, tot, msg))

    # Mock httpx.AsyncClient inside asyncio.run
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        res = runner.run_async_benchmark(urls, proxy_url="", workers=2, progress_cb=_prog)

    assert res["mode"] == "Async"
    assert res["total_requests"] == 2
    assert res["success_count"] == 2
    assert res["fail_count"] == 0
    assert len(progress_called) == 2
