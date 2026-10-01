import pytest
import tkinter as tk
from onion_search.main import create_app
from onion_search.ui.main_window import MainWindow
from onion_search.storage.sqlite_backend import SQLiteBackend
from onion_search.storage.json_backend import JSONBackend
from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher
from onion_search.core.neonym import TorController

def test_application_bootstrap():
    root = tk.Tk()
    root.withdraw()  # keep window hidden
    
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
    
    root.destroy()
