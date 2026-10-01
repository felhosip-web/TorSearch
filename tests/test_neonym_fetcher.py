import pytest
from onion_search.core.neonym import (
    find_tor_cookie,
    check_control_port,
    check_tor_socks,
    TorController,
)
from onion_search.core.fetcher import (
    SessionManager,
    OnionFetcher,
    get_session,
    close_all_thread_sessions,
)

def test_session_manager():
    mgr = SessionManager()
    s1 = mgr.get_session("socks5h://127.0.0.1:9050")
    assert s1 is not None
    assert s1.proxies["http"] == "socks5h://127.0.0.1:9050"
    
    # Switching proxy closes previous session
    s2 = mgr.get_session("socks5h://127.0.0.1:9150")
    assert s2.proxies["http"] == "socks5h://127.0.0.1:9150"
    
    mgr.close_all()

def test_tor_controller_init():
    reset_called = []
    ctrl = TorController(on_sessions_reset=lambda: reset_called.append(True))
    assert ctrl.last_newnym == 0
    # Testing socket failure on unused port
    ok, msg = ctrl.check_control(19999)
    assert ok is False
    assert "hiba" in msg or "Control" in msg

def test_onion_fetcher_init():
    fetcher = OnionFetcher()
    assert fetcher.session_manager is not None
    assert fetcher.detector is not None
