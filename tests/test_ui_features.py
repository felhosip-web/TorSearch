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

def test_panic_wipe_key_bindings(tmp_path):
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

    # Check that Ctrl+Delete and Ctrl+KP_Delete are NOT bound
    assert root.bind("<Control-Delete>") == "" or root.bind("<Control-Delete>") is None
    assert root.bind("<Control-KP_Delete>") == "" or root.bind("<Control-KP_Delete>") is None

    # Check that Ctrl+Shift+Delete, Ctrl+Shift+KP_Delete, Ctrl+Shift+BackSpace ARE bound
    assert root.bind("<Control-Shift-Delete>") != ""
    assert root.bind("<Control-Shift-KP_Delete>") != ""
    assert root.bind("<Control-Shift-BackSpace>") != ""

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


def test_main_window_tor_diagnostics(tmp_path):
    root = tk.Tk()
    root.withdraw()

    from onion_search.storage.sqlite_backend import SQLiteBackend
    from onion_search.storage.json_backend import JSONBackend
    import time

    test_db = tmp_path / "test.db"
    test_json = tmp_path / "test.json"
    test_dead = tmp_path / "dead.json"

    sqlite_backend = SQLiteBackend(db_file=test_db)
    json_backend = JSONBackend(state_file=test_json, dead_file=test_dead)

    mock_tor_controller = MagicMock()
    mock_tor_controller.run_diagnostics.return_value = {
        "success": True,
        "selected_socks_port": "9050",
        "selected_ctrl_port": "9051",
        "short_msg": "[✓] Tor OK 9050",
        "formatted_report": "OK Report",
        "ports": {},
        "control_ports": {"9051": {"ok": True, "msg": "OK"}},
        "active_res": {"latency_ms": 120.0, "ip": "1.2.3.4"},
    }

    app = MainWindow(
        root,
        sqlite_backend=sqlite_backend,
        json_backend=json_backend,
        tor_controller=mock_tor_controller,
    )

    assert app.tor_tcp_timeout_var.get() == 2.0
    assert app.tor_socks_timeout_var.get() == 4.0

    app.tor_tcp_timeout_var.set(3.0)
    app.tor_socks_timeout_var.set(6.0)
    app.save_current_config()

    app.run_tor_diagnostics_thread(show_dialog_on_success=False, force_full_scan=True)
    time.sleep(0.3)
    root.update()

    assert app.port_var.get() == "9050"
    assert app.ctrl_port_var.get() == "9051"

    root.destroy()


def test_settings_dialog_initialization_validation_and_save(tmp_path):
    root = tk.Tk()
    root.withdraw()

    from onion_search.config import ConfigManager, AppConfig
    from onion_search.ui.settings_dialog import SettingsDialog
    from unittest.mock import patch

    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_file=cfg_file)

    saved_callback_cfg = [None]
    diag_called = [False]

    def _on_save(c):
        saved_callback_cfg[0] = c

    def _on_diag():
        diag_called[0] = True

    dialog = SettingsDialog(
        parent=root,
        config_manager=mgr,
        on_save_callback=_on_save,
        on_run_diagnostics_callback=_on_diag,
    )

    assert dialog.socks_port_var.get() == "9050"
    assert dialog.workers_var.get() == 6

    # Test invalid validation
    dialog.workers_var.set(99)  # Too large (max 20)
    valid, err = dialog.validate_inputs()
    assert valid is False
    assert "Workers" in err

    # Fix worker value and test valid apply
    dialog.workers_var.set(8)
    dialog.socks_port_var.set("9150")
    dialog.tor_tcp_timeout_var.set(1.5)
    applied = dialog.apply_changes()
    assert applied is True
    assert saved_callback_cfg[0] is not None
    assert saved_callback_cfg[0].workers == 8
    assert saved_callback_cfg[0].socks_port == "9150"
    assert saved_callback_cfg[0].tor_tcp_timeout == 1.5

    # Test diagnostics callback
    dialog.run_diagnostics()
    assert diag_called[0] is True

    # Test reset to defaults
    with patch("tkinter.messagebox.askyesno", return_value=True):
        dialog.reset_to_defaults()
        assert dialog.workers_var.get() == 6
        assert dialog.socks_port_var.get() == "9050"

    dialog.win.destroy()
    root.destroy()
