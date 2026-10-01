import tempfile
import time
from pathlib import Path
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend

def test_json_backend_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        dead_file = Path(tmpdir) / "dead.json"
        backend = JSONBackend(state_file=state_file, dead_file=dead_file)
        
        assert backend.load() is None
        assert backend.load_dead() == {}
        
        data = {
            "results": [{"url": "http://sample.onion", "title": "Sample", "snippet": "text", "fp": "fp1", "ts": 1700000000.0, "lang": "en", "category": "wiki"}],
            "seen_fp": {"fp1": "http://sample.onion"},
            "seen_btc": {},
            "checked_urls": ["http://sample.onion"],
            "stats": {"total": 1, "alive": 1, "clone": 0, "dead": 0, "filtered": 0},
            "queries": "wiki",
            "extra": "",
            "success_count": 1,
            "total_count": 1,
            "total_newnym": 0
        }
        backend.save(data)
        
        loaded = backend.load()
        assert loaded is not None
        assert loaded["results"][0]["url"] == "http://sample.onion"
        assert loaded["stats"]["alive"] == 1
        
        dead_data = {
            "http://dead1.onion": time.time(),
            "http://dead2.onion": time.time() - 25 * 3600
        }
        backend.save_dead(dead_data)
        loaded_dead = backend.load_dead()
        assert "http://dead1.onion" in loaded_dead
        assert "http://dead2.onion" not in loaded_dead
        
        backend.clear()
        assert not state_file.exists()
        assert not dead_file.exists()

def test_sqlite_backend_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_onion.db"
        backend = SQLiteBackend(db_file=db_file)
        
        data = {
            "results": [
                {"url": "http://site1.onion", "title": "Site 1", "snippet": "Snippet 1", "fp": "fp_a", "ts": 1700000000.0, "lang": "hu", "category": "forum"}
            ],
            "seen_fp": {"fp_a": "http://site1.onion"},
            "seen_btc": {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa": "http://site1.onion"},
            "checked_urls": ["http://site1.onion"],
            "stats": {"total": 1, "alive": 1, "clone": 0, "dead": 0, "filtered": 0},
            "queries": "forum",
            "extra": "",
            "success_count": 3,
            "total_count": 5,
            "total_newnym": 2,
            "dead_blacklist": {"http://offline.onion": time.time()}
        }
        backend.save(data)
        
        # Test direct indexed queries
        assert backend.get_fingerprint_url("fp_a") == "http://site1.onion"
        assert backend.get_fingerprint_url("nonexistent_fp") is None
        assert backend.get_btc_url("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == "http://site1.onion"
        assert backend.get_btc_url("nonexistent_btc") is None
        assert backend.is_url_checked("http://site1.onion") is True
        assert backend.is_url_checked("http://unvisited.onion") is False
        
        loaded = backend.load()
        assert loaded is not None
        assert len(loaded["results"]) == 1
        assert loaded["results"][0]["title"] == "Site 1"
        assert loaded["seen_fp"] == {"fp_a": "http://site1.onion"}
        assert loaded["seen_btc"] == {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa": "http://site1.onion"}
        
        # Test pending incremental save
        pending = {
            "results": [
                {"url": "http://site2.onion", "title": "Site 2", "snippet": "Snippet 2", "fp": "fp_b", "ts": 1700000010.0, "lang": "en", "category": "news"}
            ],
            "seen_fp": {"fp_b": "http://site2.onion"},
            "seen_btc": {},
            "checked_urls": ["http://site2.onion"],
            "stats": {"total": 2, "alive": 2, "clone": 0, "dead": 0, "filtered": 0}
        }
        assert backend.save_pending(pending) is True
        assert backend.is_url_checked("http://site2.onion") is True
        
        # Dead blacklist
        loaded_dead = backend.load_dead()
        assert "http://offline.onion" in loaded_dead
        
        backend.cleanup_dead()
        backend.clear()
        
        loaded3 = backend.load()
        assert len(loaded3["results"]) == 0
