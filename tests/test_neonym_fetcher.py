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
    mock_session = MagicMock()
    # First response fails with 503, second response succeeds with 200
    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "Service Unavailable"
    resp_503.url = "http://test.onion"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.text = "<html><head><title>Success</title></head><body>" + ("content " * 50) + "</body></html>"
    resp_200.url = "http://test.onion"

    mock_session.get.side_effect = [resp_503, resp_200]

    mock_mgr = MagicMock()
    mock_mgr.get_session.return_value = mock_session

    fetcher = OnionFetcher(session_manager=mock_mgr, max_retries=2, domain_delay=0.0)
    res = fetcher.fetch_page("http://test.onion", "socks5h://127.0.0.1:9050")

    assert res["status"] == "ok"
    assert res["title"] == "Success"
    assert mock_session.get.call_count == 2
