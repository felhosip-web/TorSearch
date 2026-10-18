import pytest
import time
from onion_search.utils.helpers import fmt_ts, parse_list, normalize_onion_url, HEADERS_LIST, TIMEOUT_GET

def test_normalize_onion_url():
    valid_host = "abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion"
    # Rules: http scheme, lowercase host, no trailing slash on path, drop query & fragment, valid .onion
    assert normalize_onion_url(f"http://{valid_host.upper()}") == f"http://{valid_host}"
    assert normalize_onion_url(f"https://{valid_host}/") == f"http://{valid_host}"
    assert normalize_onion_url(f"{valid_host}/path/to/page/?q=1#frag") == f"http://{valid_host}/path/to/page"
    assert normalize_onion_url(f"http://{valid_host}/path///") == f"http://{valid_host}/path"
    # Invalid addresses
    assert normalize_onion_url("http://google.com") is None
    assert normalize_onion_url("http://invalid_onion.onion") is None
    assert normalize_onion_url("") is None
    assert normalize_onion_url(None) is None

def test_fmt_ts():
    assert fmt_ts(None) == ""
    assert fmt_ts("") == ""
    assert fmt_ts("invalid") == ""
    ts = 1700000000.0
    res = fmt_ts(ts)
    assert len(res) == 16
    assert ":" in res

def test_parse_list():
    assert parse_list("") == []
    assert parse_list(None) == []
    assert parse_list("  Forum, Board , WIKI ") == ["forum", "board", "wiki"]
    assert parse_list("apple") == ["apple"]

def test_constants():
    assert len(HEADERS_LIST) >= 2
    assert TIMEOUT_GET == 20
