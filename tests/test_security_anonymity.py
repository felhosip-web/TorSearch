"""
Unit tests for security and anonymity features:
- Proxy enforcement for GitHub seeds & Ahmia
- Tor-only mode (clearnet blocking)
- Cryptographic storage encryption with Fernet
- Panic wipe shredding
"""
import os
import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from onion_search.core.fetcher import OnionFetcher
from onion_search.storage.crypto import StorageEncryptor
from onion_search.storage.json_backend import JSONBackend
from onion_search.ui.main_window import MainWindow


def test_fetch_github_seeds_blocks_clearnet_when_disabled():
    fetcher = OnionFetcher()
    # Without proxy and with allow_clearnet=False, must block and return empty set
    res = fetcher.fetch_github_seeds(proxy_url=None, allow_clearnet=False)
    assert res == set()


def test_fetch_github_seeds_uses_proxy_when_provided():
    fetcher = OnionFetcher()
    mock_resp = MagicMock()
    mock_resp.text = "http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion"

    with patch("requests.get", return_value=mock_resp) as mock_get:
        proxy = "socks5h://127.0.0.1:9050"
        res = fetcher.fetch_github_seeds(proxy_url=proxy, allow_clearnet=False)
        assert len(res) >= 1
        # Verify proxies parameter was passed to requests.get
        assert mock_get.call_count >= 1
        call_kwargs = mock_get.call_args_list[0][1]
        assert call_kwargs.get("proxies") == {"http": proxy, "https": proxy}


def test_search_ahmia_blocks_clearnet_when_disabled():
    fetcher = OnionFetcher()
    res = fetcher.search_ahmia(["forum"], proxy_url=None, allow_clearnet=False)
    assert res == set()


def test_search_ahmia_routes_via_proxy():
    fetcher = OnionFetcher()
    mock_resp = MagicMock()
    mock_resp.text = '<html><body><a href="http://abcdefghijklmnopqrstuvwxyz234567abcdefghijklmnopqrstuvwx.onion">Link</a></body></html>'

    with patch("requests.get", return_value=mock_resp) as mock_get:
        proxy = "socks5h://127.0.0.1:9050"
        res = fetcher.search_ahmia(["forum"], proxy_url=proxy, allow_clearnet=False)
        assert len(res) >= 1
        call_kwargs = mock_get.call_args_list[0][1]
        assert call_kwargs.get("proxies") == {"http": proxy, "https": proxy}


def test_storage_encryptor_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        key_file = Path(tmpdir) / ".test.key"
        encryptor = StorageEncryptor(key_file=key_file)
        
        sample_data = {
            "visited": ["http://onion1.onion", "http://onion2.onion"],
            "count": 42
        }
        token = encryptor.encrypt_json(sample_data)
        assert isinstance(token, bytes)
        # Ensure plaintext URL is not visible in raw ciphertext
        assert b"http://onion1.onion" not in token

        decrypted = encryptor.decrypt_json(token)
        assert decrypted == sample_data


def test_json_backend_encrypted_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state_v3.json"
        dead_file = Path(tmpdir) / "dead.json"
        key_file = Path(tmpdir) / ".key"

        encryptor = StorageEncryptor(key_file=key_file)
        backend = JSONBackend(
            state_file=state_file,
            dead_file=dead_file,
            encrypt_storage=True,
            encryptor=encryptor,
        )

        test_state = {
            "checked_urls": ["http://secret_site1.onion"],
            "results": [{"url": "http://secret_site1.onion", "title": "Secret Site"}]
        }
        backend.save(test_state)

        # Verify on-disk file is ciphertext
        with open(state_file, "rb") as f:
            disk_content = f.read()
        assert b"secret_site1.onion" not in disk_content

        # Verify decrypts properly
        loaded = backend.load()
        assert loaded is not None
        assert loaded["checked_urls"] == ["http://secret_site1.onion"]
        assert loaded["results"][0]["title"] == "Secret Site"


def test_sqlite_backend_encrypted_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        from onion_search.storage.sqlite_backend import SQLiteBackend
        db_file = Path(tmpdir) / "onion_enc.db"
        key_file = Path(tmpdir) / ".key"

        encryptor = StorageEncryptor(key_file=key_file)
        backend = SQLiteBackend(
            db_file=db_file,
            encrypt_storage=True,
            encryptor=encryptor,
        )

        test_data = {
            "checked_urls": ["http://topsecret_site.onion"],
            "dead_blacklist": {"http://topsecret_dead.onion": time.time()},
            "results": [{"url": "http://topsecret_site.onion", "title": "Top Secret"}]
        }
        backend.save(test_data)

        # Verify that checking URL handles encrypted mapping
        assert backend.is_url_checked("http://topsecret_site.onion") is True

        # Verify on-disk SQLite does not contain plain onion address for checked/dead
        with open(db_file, "rb") as f:
            raw_db = f.read()
        assert b"topsecret_dead.onion" not in raw_db

        # Verify loaded data is transparently decrypted
        loaded = backend.load()
        assert "http://topsecret_site.onion" in loaded["checked_urls"]

        loaded_dead = backend.load_dead()
        assert "http://topsecret_dead.onion" in loaded_dead


def test_panic_wipe_shreds_files_and_resets_state():
    root = tk.Tk()
    root.withdraw()

    with tempfile.TemporaryDirectory() as tmpdir:
        from onion_search.storage.sqlite_backend import SQLiteBackend
        db_file = Path(tmpdir) / "onion.db"
        json_file = Path(tmpdir) / "state.json"
        dead_file = Path(tmpdir) / "dead.json"

        sqlite_b = SQLiteBackend(db_file=db_file)
        sqlite_b.save({"results": [{"url": "http://secret.onion"}]})
        with open(json_file, "w") as f:
            f.write("sensitive json")
        with open(dead_file, "w") as f:
            f.write("sensitive dead urls")

        json_b = JSONBackend(state_file=json_file, dead_file=dead_file)

        app = MainWindow(root, sqlite_backend=sqlite_b, json_backend=json_b)
        app.results = [{"url": "http://test.onion"}]
        app.checked_urls = {"http://test.onion"}
        app.pending_queue = ["http://test.onion"]

        # Mock messagebox.askyesno to confirm panic
        with patch("tkinter.messagebox.askyesno", return_value=True), patch("tkinter.messagebox.showinfo"):
            app.panic_wipe()

        # In-memory structures cleared
        assert len(app.results) == 0
        assert len(app.checked_urls) == 0
        assert len(app.pending_queue) == 0

        # Sensitive files were shredded
        assert not json_file.exists()
        assert not dead_file.exists()

    root.destroy()
