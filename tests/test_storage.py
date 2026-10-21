import tempfile
import time
from pathlib import Path
import os
import sys
import pytest
from onion_search.storage.crypto import StorageEncryptor
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions check")
def test_key_file_and_dir_permissions():
    with tempfile.TemporaryDirectory() as tmpdir:
        key_dir = Path(tmpdir) / "sub_config"
        key_file = key_dir / ".test.key"

        encryptor = StorageEncryptor(key_file=key_file)
        assert key_file.exists()

        file_mode = oct(os.stat(key_file).st_mode & 0o777)
        dir_mode = oct(os.stat(key_dir).st_mode & 0o777)
        assert file_mode == "0o600"
        assert dir_mode == "0o700"

        # Test tightening permissions on existing file
        os.chmod(key_file, 0o644)
        encryptor2 = StorageEncryptor(key_file=key_file)
        file_mode_after = oct(os.stat(key_file).st_mode & 0o777)
        assert file_mode_after == "0o600"

def test_pbkdf2_passphrase_key_derivation_and_legacy_fallback(caplog):
    import base64
    import hashlib
    from cryptography.fernet import Fernet

    with tempfile.TemporaryDirectory() as tmpdir:
        key_file = Path(tmpdir) / ".storage.key"
        passphrase = "my_secret_password"

        # 1. New key derivation with passphrase
        enc_new = StorageEncryptor(key=passphrase, key_file=key_file)
        token_new = enc_new.encrypt_bytes(b"hello_pbkdf2")
        assert enc_new.decrypt_bytes(token_new) == b"hello_pbkdf2"

        # Salt file created with 0o600
        salt_file = Path(tmpdir) / ".storage.salt"
        assert salt_file.exists()
        if sys.platform != "win32":
            assert oct(os.stat(salt_file).st_mode & 0o777) == "0o600"

        # 2. Legacy SHA-256 fallback test
        legacy_key = base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode("utf-8")).digest())
        legacy_fernet = Fernet(legacy_key)
        token_legacy = legacy_fernet.encrypt(b"hello_legacy")

        # enc_new using the same passphrase should decrypt legacy token and log warning
        with caplog.at_level("WARNING"):
            decrypted_legacy = enc_new.decrypt_bytes(token_legacy)
            assert decrypted_legacy == b"hello_legacy"
            assert "régi kulcsformátum" in caplog.text

        # 3. Same password + different salt -> different key
        key_file2 = Path(tmpdir) / "dir2" / ".storage.key"
        enc_other_salt = StorageEncryptor(key=passphrase, key_file=key_file2)
        assert enc_new.key != enc_other_salt.key


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions check")
def test_config_and_backend_file_permissions(tmp_path):
    from onion_search.config import ConfigManager, AppConfig

    cfg_file = tmp_path / "config.json"
    mgr = ConfigManager(config_file=cfg_file)
    mgr.save(AppConfig())

    assert cfg_file.exists()
    assert oct(os.stat(cfg_file).st_mode & 0o777) == "0o600"

    # SQLite
    db_file = tmp_path / "test.db"
    sqlite_b = SQLiteBackend(db_file=db_file)
    sqlite_b.save({"results": []})
    assert oct(os.stat(db_file).st_mode & 0o777) == "0o600"

    # JSON
    state_file = tmp_path / "state.json"
    dead_file = tmp_path / "dead.json"
    json_b = JSONBackend(state_file=state_file, dead_file=dead_file)
    json_b.save({"results": []})
    json_b.save_dead({"http://dead.onion": time.time()})
    assert oct(os.stat(state_file).st_mode & 0o777) == "0o600"
    assert oct(os.stat(dead_file).st_mode & 0o777) == "0o600"


def test_sqlite_like_escaping():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_like.db"
        backend = SQLiteBackend(db_file=db_file)

        data = {
            "results": [
                {"url": "http://site1.onion", "title": "Discount 100% sale", "snippet": "Text", "fp": "fp1", "ts": 100.0},
                {"url": "http://site2.onion", "title": "Discount 1000 sale", "snippet": "Text", "fp": "fp2", "ts": 100.0},
                {"url": "http://site3.onion", "title": "a_b item", "snippet": "Text", "fp": "fp3", "ts": 100.0},
                {"url": "http://site4.onion", "title": "axb item", "snippet": "Text", "fp": "fp4", "ts": 100.0},
            ]
        }
        backend.save(data)

        # Search "100%" should only match "Discount 100% sale", not "Discount 1000 sale"
        res_percent, total_pct = backend.get_results(query="100%")
        assert total_pct == 1
        assert res_percent[0]["title"] == "Discount 100% sale"

        # Search "a_b" should only match "a_b item", not "axb item"
        res_underscore, total_und = backend.get_results(query="a_b")
        assert total_und == 1
        assert res_underscore[0]["title"] == "a_b item"


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
