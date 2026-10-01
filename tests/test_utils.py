import pytest
import time
from onion_search.utils.helpers import fmt_ts, parse_list, HEADERS_LIST, TIMEOUT_GET

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
