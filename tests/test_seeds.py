"""
Unit tests for multi-source automated seed discovery (Tor66, Deep Search, Ahmia, GitHub, OSE).
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from onion_search.core.fetcher import OnionFetcher
from onion_search.core.seeds import SeedManager, extract_onion_urls


def test_extract_onion_urls():
    u1 = "http://" + "a" * 56 + ".onion"
    u2 = "https://" + "b" * 56 + ".onion/fresh"
    u3 = "HTTP://" + "C" * 56 + ".ONION"
    text = f"Here are some sites: {u1} and {u2} and invalid_onion.onion and uppercase {u3}"
    extracted = extract_onion_urls(text)
    assert len(extracted) == 3
    assert ("http://" + "a" * 56 + ".onion") in extracted
    assert ("http://" + "b" * 56 + ".onion") in extracted
    assert ("http://" + "c" * 56 + ".onion") in extracted


def test_seed_manager_cache_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "seeds_cache.json"
        mgr = SeedManager(cache_file=cache_file)
        assert mgr.is_update_due() is True

        sample_seeds = {
            "http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion",
            "http://tor66sewebgixwhcqfnpq5wfsqxuvhn2bawa4rwfdgahforacxdad.onion",
        }
        source_counts = {"tor66": 1, "deepsearch": 1}
        assert mgr.save_cache(sample_seeds, source_counts=source_counts) is True
        assert cache_file.exists()

        # Reload cache in fresh manager
        mgr2 = SeedManager(cache_file=cache_file)
        assert mgr2.cached_seeds == sample_seeds
        assert mgr2.is_update_due(interval_hours=12.0) is False


def test_seed_manager_tor66_fetch():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "seeds_cache.json"
        mgr = SeedManager(cache_file=cache_file)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = (
            "<html><body>"
            "<a href='http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion'>Site 1</a>"
            "<a href='http://tor66sewebgixwhcqfnpq5wfsqxuvhn2bawa4rwfdgahforacxdad.onion'>Tor66 Link</a>"
            "</body></html>"
        )

        with patch("requests.get", return_value=mock_resp) as mock_get:
            proxy = "socks5h://127.0.0.1:9050"
            res = mgr.fetch_tor66(proxy_url=proxy, allow_clearnet=False)
            assert len(res) == 2
            assert mock_get.called
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs["proxies"] == {"http": proxy, "https": proxy}


def test_seed_manager_deepsearch_fetch():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "seeds_cache.json"
        mgr = SeedManager(cache_file=cache_file)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = (
            "<html><body>"
            "<a href='http://deepsearch74sxv42abcdefghijklmnopqrstuvwxyz234567abcdefg.onion'>Deep Search Result</a>"
            "</body></html>"
        )

        with patch("requests.get", return_value=mock_resp):
            proxy = "socks5h://127.0.0.1:9050"
            res = mgr.fetch_deepsearch(proxy_url=proxy, allow_clearnet=False)
            assert len(res) == 1
            assert "http://deepsearch74sxv42abcdefghijklmnopqrstuvwxyz234567abcdefg.onion" in res


def test_seed_manager_fetch_all_and_caching():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = Path(tmpdir) / "seeds_cache.json"
        mgr = SeedManager(cache_file=cache_file)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion"

        with patch("requests.get", return_value=mock_resp):
            progress_calls = []

            def _on_progress(src, cnt):
                progress_calls.append((src, cnt))

            proxy = "socks5h://127.0.0.1:9050"
            all_seeds, counts = mgr.fetch_all(
                proxy_url=proxy,
                allow_clearnet=False,
                selected_sources=["tor66", "deepsearch"],
                on_source_progress=_on_progress,
            )
            assert len(all_seeds) >= 1
            assert "tor66" in counts
            assert "deepsearch" in counts
            assert len(progress_calls) == 2
            # Verify cache was written
            assert cache_file.exists()


def test_onion_fetcher_seed_delegation():
    fetcher = OnionFetcher()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion"

    with patch("requests.get", return_value=mock_resp):
        proxy = "socks5h://127.0.0.1:9050"
        tor66_res = fetcher.fetch_tor66_seeds(proxy_url=proxy, allow_clearnet=False)
        assert len(tor66_res) >= 1

        deep_res = fetcher.fetch_deepsearch_seeds(proxy_url=proxy, allow_clearnet=False)
        assert len(deep_res) >= 1

        all_res, counts = fetcher.fetch_all_seeds(
            proxy_url=proxy, allow_clearnet=False, selected_sources=["tor66"]
        )
        assert len(all_res) >= 1
        assert "tor66" in counts


def test_seed_ui_dialog_and_periodic_updater():
    import tkinter as tk
    from onion_search.ui.main_window import MainWindow

    root = tk.Tk()
    root.withdraw()
    app = MainWindow(root)

    # Verify buttons and config button
    assert hasattr(app, "btn_seeds")
    assert hasattr(app, "btn_seeds_cfg")
    assert app.auto_seed_var.get() is True

    # Open seeds dialog
    app.open_seeds_dialog()
    root.update()

    # Find opened dialog window
    toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(toplevels) >= 1
    dlg = toplevels[-1]
    assert "Maglista" in dlg.title()

    # Test periodic update execution safely
    with patch.object(app, "update_seeds_thread") as mock_update:
        app.fetcher.seed_manager.last_update_ts = 0.0  # Force due
        app.schedule_periodic_seed_update()
        assert mock_update.called

    dlg.destroy()
    root.destroy()

