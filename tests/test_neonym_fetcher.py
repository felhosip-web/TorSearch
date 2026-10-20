import pytest
import time
from unittest.mock import MagicMock, patch
from onion_search.core.neonym import (
    find_tor_cookie,
    check_control_port,
    check_tor_socks,
    TorController,
)
from onion_search.core.fetcher import (
    SessionManager,
    OnionFetcher,
    DomainRateLimiter,
    RobotsChecker,
    get_session,
    close_all_thread_sessions,
)

def test_session_manager():
    mgr = SessionManager()
    s1 = mgr.get_session("socks5h://127.0.0.1:9050")
    assert s1 is not None
    assert s1.proxies["http"] == "socks5h://127.0.0.1:9050"
    
    s2 = mgr.get_session("socks5h://127.0.0.1:9150")
    assert s2.proxies["http"] == "socks5h://127.0.0.1:9150"
    mgr.close_all()

def test_domain_rate_limiter():
    limiter = DomainRateLimiter(min_domain_delay=0.1)
    domain = "example3g75bv652.onion"
    
    t0 = time.time()
    limiter.wait_for_domain(domain)
    limiter.wait_for_domain(domain)
    elapsed = time.time() - t0
    
    # Must have waited at least ~0.08s
    assert elapsed >= 0.08

def test_robots_checker_disabled():
    checker = RobotsChecker(enabled=False)
    assert checker.is_allowed("http://example.onion/private", sess=None) is True

def test_onion_fetcher_retry_logic():
    # First response fails with 503, second response succeeds with 200
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "Service Unavailable"
    resp_503.url = "http://test.onion"
    resp_503.headers = {}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.text = "<html><head><title>Success</title></head><body>" + ("content " * 50) + "</body></html>"
    resp_200.url = "http://test.onion"
    resp_200.headers = {}
    resp_200.iter_content.return_value = [resp_200.text.encode("utf-8")]

    with patch("requests.get", side_effect=[resp_503, resp_200]) as mock_get:
        fetcher = OnionFetcher(max_retries=2, domain_delay=0.0)
        res = fetcher.fetch_page("http://test.onion", "socks5h://127.0.0.1:9050")

        assert res["status"] == "ok"
        assert res["title"] == "Success"
        assert mock_get.call_count == 2


def test_probe_tor_socks_port_refused():
    with patch("socket.socket") as mock_sock:
        mock_s = MagicMock()
        mock_s.connect.side_effect = ConnectionRefusedError(111, "Connection refused")
        mock_sock.return_value = mock_s

        from onion_search.core.neonym import probe_tor_socks_port
        res = probe_tor_socks_port(9050, tcp_timeout=1.0, socks_timeout=2.0)
        assert res["tcp_open"] is False
        assert res["socks_ok"] is False
        assert "Connection refused" in res["error"]


def test_probe_tor_socks_port_success():
    with patch("socket.socket") as mock_sock, patch("requests.get") as mock_get:
        mock_s = MagicMock()
        mock_sock.return_value = mock_s

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"IsTor": True, "IP": "185.220.101.4"}
        mock_get.return_value = mock_resp

        from onion_search.core.neonym import probe_tor_socks_port
        res = probe_tor_socks_port(9050, tcp_timeout=1.0, socks_timeout=2.0)
        assert res["tcp_open"] is True
        assert res["socks_ok"] is True
        assert res["is_tor"] is True
        assert res["ip"] == "185.220.101.4"
        assert res["latency_ms"] is not None


def test_run_tor_diagnostics_fast_path():
    with patch("onion_search.core.neonym.probe_tor_socks_port") as mock_probe, \
         patch("onion_search.core.neonym.check_control_port") as mock_ctrl:
        mock_probe.return_value = {
            "port": "9150", "tcp_open": True, "socks_ok": True, "is_tor": True, "latency_ms": 120.0, "ip": "1.2.3.4", "status_str": "működik (120 ms)"
        }
        mock_ctrl.return_value = (True, "ControlPort OK")

        from onion_search.core.neonym import run_tor_diagnostics
        diag = run_tor_diagnostics(preferred_port="9150", force_full_scan=False)
        assert diag["success"] is True
        assert diag["selected_socks_port"] == "9150"
        assert mock_probe.call_count == 1  # Fast path checked only preferred port!


def test_run_tor_diagnostics_force_full_scan():
    with patch("onion_search.core.neonym.probe_tor_socks_port") as mock_probe, \
         patch("onion_search.core.neonym.check_control_port") as mock_ctrl:
        mock_probe.side_effect = [
            {"port": "9050", "tcp_open": True, "socks_ok": True, "is_tor": True, "latency_ms": 150.0, "ip": "1.2.3.4", "status_str": "működik (150 ms)"},
            {"port": "9150", "tcp_open": True, "socks_ok": True, "is_tor": True, "latency_ms": 180.0, "ip": "1.2.3.4", "status_str": "működik (180 ms)"},
        ]
        mock_ctrl.return_value = (True, "ControlPort OK")

        from onion_search.core.neonym import run_tor_diagnostics, TorController
        diag = run_tor_diagnostics(preferred_port="9050", force_full_scan=True)
        assert diag["success"] is True
        assert diag["selected_socks_port"] == "9050"
        assert mock_probe.call_count == 2  # Forced full scan checked both ports!


def test_run_tor_diagnostics_failure():
    with patch("onion_search.core.neonym.probe_tor_socks_port") as mock_probe, \
         patch("onion_search.core.neonym.check_control_port") as mock_ctrl:
        mock_probe.side_effect = [
            {"port": "9050", "tcp_open": False, "socks_ok": False, "is_tor": False, "latency_ms": None, "ip": None, "status_str": "nem elérhető (Connection refused)"},
            {"port": "9150", "tcp_open": False, "socks_ok": False, "is_tor": False, "latency_ms": None, "ip": None, "status_str": "nem elérhető (Connection refused)"},
        ]
        mock_ctrl.return_value = (False, "Connection refused")

        from onion_search.core.neonym import run_tor_diagnostics
        diag = run_tor_diagnostics()
        assert diag["success"] is False
        assert diag["selected_socks_port"] is None
        assert "Tor kapcsolat sikertelen" in diag["formatted_report"]
        assert "sudo systemctl start tor" in diag["formatted_report"]
