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
Comprehensive Unit Tests for Seed Plugin Architecture, Registry, Orchestrator,
Health Check Caching, and UI Integrations.
"""
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.seeds.orchestrator import SeedOrchestrator
from onion_search.seeds.plugins.custom_regex import CustomUrlRegexPlugin
from onion_search.seeds.plugins.tor66 import Tor66Plugin
from onion_search.seeds.registry import PluginRegistry


class MockSuccessPlugin(BaseSeedPlugin):
    id = "mock_success"
    name = "Mock Success Plugin"
    priority = 10

    def _do_fetch_seeds(self, query=None, proxy_url=None, allow_clearnet=False, timeout=15):
        return {"http://" + "a" * 56 + ".onion", "http://" + "b" * 56 + ".onion"}

    def _do_health_check(self, proxy_url=None, allow_clearnet=False):
        return True, "Mock OK"


class MockFailingPlugin(BaseSeedPlugin):
    id = "mock_failing"
    name = "Mock Failing Plugin"
    priority = 5

    def _do_fetch_seeds(self, query=None, proxy_url=None, allow_clearnet=False, timeout=15):
        raise RuntimeError("Connection reset by peer")

    def _do_health_check(self, proxy_url=None, allow_clearnet=False):
        return False, "Unreachable"


def test_base_plugin_health_check_caching():
    plugin = MockSuccessPlugin()
    assert plugin._health_last_check == 0.0

    ok, msg = plugin.health_check(force=False)
    assert ok is True
    assert msg == "Mock OK"
    last_check_ts = plugin._health_last_check
    assert last_check_ts > 0

    # Second call within TTL should return cached status without re-running _do_health_check
    with patch.object(plugin, "_do_health_check") as mock_hc:
        ok2, msg2 = plugin.health_check(force=False)
        assert ok2 is True
        assert msg2 == "Mock OK"
        assert not mock_hc.called

    # Forced call should re-run _do_health_check
    with patch.object(plugin, "_do_health_check", return_value=(True, "Refreshed")) as mock_hc:
        ok3, msg3 = plugin.health_check(force=True)
        assert ok3 is True
        assert msg3 == "Refreshed"
        assert mock_hc.called


def test_plugin_registry_discovery():
    reg = PluginRegistry()
    assert len(reg.get_all_plugins()) == 0

    reg.discover_plugins()
    plugins = reg.get_all_plugins()
    assert len(plugins) >= 8  # tor66, deepsearch, haystak, onionland, github, ose, torch, notevil, ahmia...

    # Verify priority ordering
    priorities = [p.priority for p in plugins]
    assert priorities == sorted(priorities)

    # Verify getting specific plugin
    tor66 = reg.get_plugin("tor66")
    assert tor66 is not None
    assert tor66.id == "tor66"

    # Test filtering disabled plugins
    enabled = reg.get_enabled_plugins(disabled_ids=["tor66"])
    enabled_ids = [p.id for p in enabled]
    assert "tor66" not in enabled_ids


def test_orchestrator_priority_cascade_and_fallback():
    reg = PluginRegistry()
    p_fail = MockFailingPlugin()  # Priority 5
    p_succ = MockSuccessPlugin()  # Priority 10
    reg.register(p_fail)
    reg.register(p_succ)

    orchestrator = SeedOrchestrator(plugin_registry=reg)
    seeds, counts = orchestrator.fetch_all(min_yield_threshold=2)

    # p_fail runs first (Prio 5), throws error, recorded as 0, orchestrator cascades to p_succ (Prio 10)
    assert counts["mock_failing"] == 0
    assert counts["mock_success"] == 2
    assert len(seeds) == 2


def test_orchestrator_use_only_healthy_sources():
    reg = PluginRegistry()
    p_fail = MockFailingPlugin()  # Priority 5 (Health Check returns False)
    p_succ = MockSuccessPlugin()  # Priority 10 (Health Check returns True)
    reg.register(p_fail)
    reg.register(p_succ)

    orchestrator = SeedOrchestrator(plugin_registry=reg)

    with patch.object(p_fail, "fetch_seeds") as mock_fail_fetch:
        seeds, counts = orchestrator.fetch_all(use_only_healthy=True)
        # p_fail should be skipped by health check before fetch_seeds is ever called
        assert not mock_fail_fetch.called
        assert counts["mock_failing"] == 0
        assert counts["mock_success"] == 2


def test_custom_url_regex_plugin():
    u1 = "http://" + "c" * 56 + ".onion"
    mock_html = f"<html><body>Check this out: <a href='{u1}'>Link</a></body></html>"

    plugin = CustomUrlRegexPlugin(target_url="https://example-directory.com/list")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html

    with patch.object(plugin, "_make_request", return_value=mock_resp):
        seeds = plugin.fetch_seeds(allow_clearnet=True)
        assert u1 in seeds


def test_tor66_plugin_mocked_fetch():
    plugin = Tor66Plugin()
    u1 = "http://" + "d" * 56 + ".onion"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = f"Found site: {u1}"

    with patch("requests.get", return_value=mock_resp):
        seeds = plugin.fetch_seeds(proxy_url="socks5h://127.0.0.1:9050")
        assert u1 in seeds
        assert plugin.last_seed_count == 1
        assert plugin.last_success > 0


def test_gui_seed_manager_dialog_and_health_checks():
    import tkinter as tk
    from onion_search.ui.main_window import MainWindow

    root = tk.Tk()
    root.withdraw()
    app = MainWindow(root)

    app.open_seeds_dialog()
    root.update()

    toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(toplevels) >= 1
    dlg = toplevels[-1]
    assert "Plugin" in dlg.title() or "Maglista" in dlg.title()

    dlg.destroy()
    root.destroy()
