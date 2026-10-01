import pytest
import tkinter as tk
from unittest.mock import MagicMock
from onion_search.main import create_app
from onion_search.ui.main_window import MainWindow
from onion_search.storage.sqlite_backend import SQLiteBackend
from onion_search.storage.json_backend import JSONBackend
from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher
from onion_search.core.neonym import TorController

def test_application_bootstrap():
    root = tk.Tk()
    root.withdraw()
    
    root_ret, app = create_app(root=root)
    assert root_ret is root
    assert isinstance(app, MainWindow)
    assert isinstance(app.sqlite_backend, SQLiteBackend)
    assert isinstance(app.json_backend, JSONBackend)
    assert isinstance(app.detector, ContentDetector)
    assert isinstance(app.fetcher, OnionFetcher)
    assert isinstance(app.tor_controller, TorController)
    assert app.filters_panel is not None
    assert app.log_panel is not None
    
    # Test UI filter synchronization
    app.filters_panel.lang_filter_var.set("hu")
    app.apply_filters()
    
    # Test bounded memory cache and DB fallback
    app.sqlite_backend.get_fingerprint_url = MagicMock(return_value="http://cached-db.onion")
    is_seen, url = app.is_fp_seen("db_only_fp")
    assert is_seen is True
    assert url == "http://cached-db.onion"
    assert "db_only_fp" in app.seen_fp
    
    # Test safe stop and resume (cancelled item does not enter checked_urls)
    app.running = False
    app.fetcher.fetch_page = MagicMock(return_value={"url": "http://interrupted.onion", "status": "canceled"})
    res = app.fetch_one("http://interrupted.onion", "socks5h://127.0.0.1:9050")
    assert res["status"] == "canceled"
    assert "http://interrupted.onion" not in app.checked_urls
    
    root.destroy()
