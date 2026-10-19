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
Unit tests for Abstract Storage Architecture (BaseStorage), SQLiteStorage batch operations,
LIMIT/OFFSET pagination, StorageFactory, and PostgresStorage skeleton.
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from onion_search.config import AppConfig
from onion_search.storage.base import BaseStorage
from onion_search.storage.factory import StorageFactory
from onion_search.storage.postgres_skeleton import PostgresStorage
from onion_search.storage.sqlite_backend import SQLiteStorage


def test_sqlite_storage_batch_and_pagination():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_onion.db"
        storage = SQLiteStorage(db_file=db_file)

        # Batch insert 25 sample results
        sample_results = [
            {
                "url": f"http://{'a' * 55}{i}.onion",
                "title": f"Site Title {i}",
                "snippet": f"Content snippet for site number {i}",
                "fp": f"fingerprint_{i}",
                "ts": time.time() - i * 10,
                "lang": "hu" if i % 2 == 0 else "en",
                "category": "forum" if i % 3 == 0 else "wiki",
            }
            for i in range(25)
        ]

        assert storage.add_results_batch(sample_results) is True

        # Query page 1 (limit=10, offset=0)
        page1, total1 = storage.get_results(limit=10, offset=0)
        assert total1 == 25
        assert len(page1) == 10

        # Query page 2 (limit=10, offset=10)
        page2, total2 = storage.get_results(limit=10, offset=10)
        assert total2 == 25
        assert len(page2) == 10
        assert page1[0]["url"] != page2[0]["url"]

        # Filter query by language and category
        hu_forums, hu_total = storage.get_results(lang="hu", category="forum", limit=50)
        assert hu_total > 0
        assert all(r["lang"] == "hu" and r["category"] == "forum" for r in hu_forums)

        # Storage statistics
        stats = storage.get_stats()
        assert stats["backend"] == "sqlite"
        assert stats["active_results"] == 25
        assert stats["db_size_bytes"] > 0


def test_sqlite_storage_dead_links_and_cleanup():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_onion.db"
        storage = SQLiteStorage(db_file=db_file)

        dead_url = "http://" + "d" * 56 + ".onion"
        assert storage.is_dead(dead_url) is False

        storage.mark_dead(dead_url, ts=time.time())
        assert storage.is_dead(dead_url) is True

        # Test cleanup with old cutoff
        expired_url = "http://" + "e" * 56 + ".onion"
        old_ts = time.time() - (48 * 3600)  # 48 hours ago
        storage.save_dead_pending({expired_url: old_ts})

        cleaned = storage.cleanup_dead(cutoff_hours=24.0)
        assert cleaned >= 1


def test_storage_export():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "test_onion.db"
        storage = SQLiteStorage(db_file=db_file)

        u1 = "http://" + "x" * 56 + ".onion"
        storage.add_result({
            "url": u1,
            "title": "Export Test",
            "snippet": "Snippet content",
            "fp": "fp_export",
            "ts": time.time(),
            "lang": "en",
            "category": "library",
        })

        # Test CSV export
        csv_path = Path(tmpdir) / "export.csv"
        assert storage.export(csv_path, format="csv") is True
        assert csv_path.exists()
        assert u1 in csv_path.read_text(encoding="utf-8")

        # Test JSON export
        json_path = Path(tmpdir) / "export.json"
        assert storage.export(json_path, format="json") is True
        assert json_path.exists()
        exported_data = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(exported_data) == 1
        assert exported_data[0]["url"] == u1


def test_storage_factory_creation():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_file = Path(tmpdir) / "factory_test.db"

        # Create SQLite backend via factory
        sqlite_inst = StorageFactory.create("sqlite", db_file=db_file)
        assert isinstance(sqlite_inst, BaseStorage)
        assert sqlite_inst.get_stats()["backend"] == "sqlite"

        # Create JSON backend via factory
        json_inst = StorageFactory.create("json", db_file=db_file)
        assert isinstance(json_inst, BaseStorage)

        # Create Postgres skeleton via factory
        pg_inst = StorageFactory.create("postgres")
        assert isinstance(pg_inst, BaseStorage)
        assert pg_inst.get_stats()["backend"] == "postgresql"

        # Create from AppConfig
        cfg = AppConfig(backend="sqlite", encrypt_storage=True)
        config_inst = StorageFactory.from_config(cfg, db_file=db_file)
        assert isinstance(config_inst, BaseStorage)


def test_postgres_storage_skeleton():
    pg = PostgresStorage(connection_uri="postgresql://localhost:5432/test_db")
    u1 = "http://" + "p" * 56 + ".onion"

    assert pg.add_result({"url": u1, "title": "PG Test", "snippet": "PG content"}) is True
    results, total = pg.get_results(query="PG")
    assert total == 1
    assert results[0]["url"] == u1

    stats = pg.get_stats()
    assert stats["backend"] == "postgresql"
    assert stats["active_results"] == 1
