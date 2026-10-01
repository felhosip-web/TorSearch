import pytest
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher, HTML_PARSER
from onion_search.storage.sqlite_backend import SQLiteBackend

def test_lxml_parser_active():
    """Verify that the faster lxml parser is enabled."""
    assert HTML_PARSER == "lxml"

def test_fingerprint_classification_caching():
    detector = ContentDetector()
    fp = "test_fingerprint_123"
    
    # First call: calculates and caches
    lang1, cat1 = detector.classify_with_cache(
        fp=fp, title="Discussion Forum", text="threads and board topics discussions"
    )
    assert lang1 == "en"
    assert cat1 == "forum"
    
    # Verify cache entry
    cached = detector.get_cached_classification(fp)
    assert cached == (lang1, cat1)
    
    # Second call with dummy text returns cached result without recalculating
    lang2, cat2 = detector.classify_with_cache(
        fp=fp, title="Different Title", text="completely different content"
    )
    assert lang2 == lang1
    assert cat2 == cat1

def test_database_indexes_created():
    """Verify that all required performance indexes exist in the SQLite database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "indexed.db"
        backend = SQLiteBackend(db_file=db_path)
        
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = set(row[0] for row in cur.fetchall())
        con.close()
        
        assert "idx_results_lang" in indexes
        assert "idx_results_cat" in indexes
        assert "idx_results_ts" in indexes
        assert "idx_results_fp" in indexes

def test_async_fetch_page_with_lxml_and_cache():
    import asyncio
    async def _run():
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><head><title>Async Onion</title></head><body>" + ("content word " * 60) + "</body></html>"
        mock_resp.url = "http://asyncsite.onion"
        mock_client.get.return_value = mock_resp

        detector = ContentDetector()
        fetcher = OnionFetcher(detector=detector)

        res = await fetcher.async_fetch_page(mock_client, "http://asyncsite.onion")
        assert res["status"] == "ok"
        assert res["title"] == "Async Onion"
        assert res["fp"] is not None

        # Verify classification was stored in detector cache
        assert detector.get_cached_classification(res["fp"]) is not None

    asyncio.run(_run())
