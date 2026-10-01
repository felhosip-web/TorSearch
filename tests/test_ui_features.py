import pytest
import tkinter as tk
from unittest.mock import MagicMock
from onion_search.ui.filters import FilterPanel
from onion_search.ui.log_panel import LogPanel
from onion_search.ui.main_window import MainWindow

def test_filter_panel_live_filtering():
    root = tk.Tk()
    root.withdraw()
    
    change_count = [0]
    def on_change():
        change_count[0] += 1

    panel = FilterPanel(root, on_filter_changed=on_change)
    assert panel.live_filter_var.get() is True
    
    # Typing in a filter entry triggers live change callback
    panel.must_all_var.set("test_kw")
    root.update()
    assert change_count[0] >= 1

    # Disabling live filtering prevents automatic triggers
    panel.live_filter_var.set(False)
    current_count = change_count[0]
    panel.must_all_var.set("another_kw")
    root.update()
    assert change_count[0] == current_count

    root.destroy()

def test_log_panel_search_and_category_filtering():
    root = tk.Tk()
    root.withdraw()
    
    log_panel = LogPanel(root)
    log_panel.log_msg("[OK] Success Onion Site 1", force=True, tag="ok")
    log_panel.log_msg("[-] HALOTT: Dead Onion Site 2", force=True, tag="dead")
    log_panel.log_msg("[NEWNYM] Circuit switched", force=True, tag="newnym")
    root.update()

    assert len(log_panel.log_history) == 3

    # Filter only errors
    log_panel.category_var.set("error")
    log_panel.refresh_view()
    root.update()
    visible_text = log_panel.log_text.get("1.0", tk.END)
    assert "HALOTT" in visible_text
    assert "Success Onion" not in visible_text

    # Search filter
    log_panel.category_var.set("all")
    log_panel.search_var.set("circuit")
    log_panel.refresh_view()
    root.update()
    visible_text = log_panel.log_text.get("1.0", tk.END)
    assert "Circuit" in visible_text
    assert "HALOTT" not in visible_text

    root.destroy()

def test_main_window_dark_mode_and_resume(tmp_path):
    root = tk.Tk()
    root.withdraw()

    from onion_search.storage.sqlite_backend import SQLiteBackend
    from onion_search.storage.json_backend import JSONBackend
    test_db = tmp_path / "test.db"
    test_json = tmp_path / "test.json"
    test_dead = tmp_path / "dead.json"

    sqlite_backend = SQLiteBackend(db_file=test_db)
    json_backend = JSONBackend(state_file=test_json, dead_file=test_dead)

    app = MainWindow(root, sqlite_backend=sqlite_backend, json_backend=json_backend)
    assert app.dark_mode_var.get() is True

    # Toggle theme
    app.toggle_theme()
    assert app.dark_mode_var.get() is False
    assert "Sötét" in app.btn_theme.cget("text")

    app.toggle_theme()
    assert app.dark_mode_var.get() is True
    assert "Világos" in app.btn_theme.cget("text")

    # Test pending queue resume enablement with fresh backend
    assert str(app.btn_resume.cget("state")) == "disabled"
    app.pending_queue = ["http://onion1.onion", "http://onion2.onion"]
    app.save_state(silent=True)

    # When loaded with queue, resume button activates
    app.load_state(silent=True)
    assert len(app.pending_queue) == 2
    assert str(app.btn_resume.cget("state")) == "normal"

    root.destroy()
