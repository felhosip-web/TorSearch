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
SQLite storage backend implementing BaseStorage abstract protocol with Fernet/HMAC encryption,
WAL mode, busy_timeout locks, secondary indexing, and paginated query execution.
Developed by HES Projects by FePe.
"""
import hashlib
import hmac
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from onion_search.storage.base import BaseStorage
from onion_search.storage.crypto import StorageEncryptor
from onion_search.utils.helpers import DB_FILE

logger = logging.getLogger("onion_search")


class SQLiteStorage(BaseStorage):
    """
    High-performance, encrypted SQLite storage backend implementing BaseStorage.
    Supports WAL mode, 5s busy timeouts, batch operations, HMAC search keys,
    and memory-efficient LIMIT/OFFSET pagination.
    """

    def __init__(
        self,
        db_file: Union[str, Path] = DB_FILE,
        encrypt_storage: bool = False,
        encryptor: Optional[StorageEncryptor] = None,
        **kwargs: Any,
    ) -> None:
        self.db_file = Path(db_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self.encrypt_storage = encrypt_storage
        self.encryptor = encryptor or (StorageEncryptor() if encrypt_storage else None)
        self.init_db()

    def _get_connection(self, read_only: bool = False) -> sqlite3.Connection:
        """Create configured sqlite3 connection with WAL mode and busy timeout."""
        if read_only and self.db_file.exists():
            con = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True, timeout=10.0)
        else:
            con = sqlite3.connect(self.db_file, timeout=10.0)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.execute("PRAGMA busy_timeout=5000;")
        return con

    def _enc_url(self, url: str) -> str:
        """Encrypt URL string if storage encryption is enabled, with keyed HMAC prefix for indexing."""
        if not self.encrypt_storage or not self.encryptor or not url:
            return url
        if url.startswith("enc:"):
            return url
        try:
            mac = hmac.new(self.encryptor.key, url.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
            cipher = self.encryptor.encrypt_bytes(url.encode("utf-8")).decode("utf-8")
            return f"enc:{mac}:{cipher}"
        except Exception:
            return url

    def _dec_url(self, stored: str) -> str:
        """Decrypt URL string if it was encrypted with Fernet."""
        if not stored or not stored.startswith("enc:"):
            return stored
        if not self.encryptor:
            return stored
        try:
            parts = stored.split(":", 2)
            cipher = parts[2] if len(parts) == 3 else parts[1]
            return self.encryptor.decrypt_bytes(cipher.encode("utf-8")).decode("utf-8")
        except Exception:
            return stored

    def _get_url_mac_pattern(self, url: str) -> str:
        if not self.encrypt_storage or not self.encryptor or not url:
            return url
        mac = hmac.new(self.encryptor.key, url.encode("utf-8"), hashlib.sha256).hexdigest()[:24]
        return f"enc:{mac}:%"

    def init_db(self) -> None:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            import os
            os.chmod(self.db_file.parent, 0o700)
        except Exception:
            pass
        con = self._get_connection()
        try:
            import os
            if self.db_file.exists():
                os.chmod(self.db_file, 0o600)
        except Exception:
            pass
        cur = con.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS results ("
            "url TEXT PRIMARY KEY, title TEXT, snippet TEXT, fp TEXT, "
            "ts REAL, lang TEXT, category TEXT)"
        )
        try:
            cur.execute("SELECT lang FROM results LIMIT 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE results ADD COLUMN lang TEXT")
            except Exception:
                pass
        try:
            cur.execute("SELECT category FROM results LIMIT 1")
        except Exception:
            try:
                cur.execute("ALTER TABLE results ADD COLUMN category TEXT")
            except Exception:
                pass
        cur.execute("CREATE TABLE IF NOT EXISTS fingerprints (fp TEXT PRIMARY KEY, url TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS btc_map (btc TEXT PRIMARY KEY, url TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS checked (url TEXT PRIMARY KEY, ts REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS dead (url TEXT PRIMARY KEY, ts REAL)")
        cur.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

        # Secondary indexes for fast filtering, pagination, and lookups
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_lang ON results(lang)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_cat ON results(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_fp ON results(fp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_checked_url ON checked(url)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dead_ts ON dead(ts)")

        con.commit()
        con.close()

    def add_result(self, result: Dict[str, Any]) -> bool:
        """Insert or update a single search result record."""
        return self.add_results_batch([result])

    def add_results_batch(self, results: List[Dict[str, Any]]) -> bool:
        """Insert or update a batch of search result records atomically."""
        if not results:
            return True
        con = self._get_connection()
        cur = con.cursor()
        try:
            cur.execute("BEGIN")
            params = [
                (
                    r["url"],
                    r.get("title", ""),
                    r.get("snippet", "")[:500],
                    r.get("fp", ""),
                    r.get("ts", time.time()),
                    r.get("lang", "en"),
                    r.get("category", "other"),
                )
                for r in results
            ]
            cur.executemany(
                "INSERT OR REPLACE INTO results (url,title,snippet,fp,ts,lang,category) "
                "VALUES (?,?,?,?,?,?,?)",
                params,
            )
            con.commit()
            con.close()
            return True
        except Exception as e:
            logger.error(f"[SQLITE STORAGE] Error batch inserting results: {e}")
            try:
                con.rollback()
                con.close()
            except Exception:
                pass
            return False

    def get_results(
        self,
        query: Optional[str] = None,
        lang: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Query results with filtering and memory-efficient limit/offset pagination.
        Returns tuple: (list of result dicts, total matching count).
        """
        if not self.db_file.exists():
            return [], 0

        con = self._get_connection(read_only=True)
        cur = con.cursor()

        where_clauses = []
        sql_params: List[Any] = []

        if lang and lang != "all":
            where_clauses.append("lang = ?")
            sql_params.append(lang)

        if category and category != "all":
            where_clauses.append("category = ?")
            sql_params.append(category)

        if query:
            escaped_q = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where_clauses.append("(title LIKE ? ESCAPE '\\' OR snippet LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\')")
            q_pat = f"%{escaped_q}%"
            sql_params.extend([q_pat, q_pat, q_pat])

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total count query
        count_sql = f"SELECT COUNT(*) FROM results{where_sql}"
        cur.execute(count_sql, sql_params)
        total_count = cur.fetchone()[0]

        # Paginated data query
        query_sql = (
            f"SELECT url,title,snippet,fp,ts,lang,category FROM results"
            f"{where_sql} ORDER BY ts DESC LIMIT ? OFFSET ?"
        )
        paginated_params = list(sql_params) + [limit, offset]
        cur.execute(query_sql, paginated_params)

        rows = cur.fetchall()
        results = [
            {
                "url": r[0],
                "title": r[1],
                "snippet": r[2],
                "fp": r[3],
                "ts": r[4],
                "lang": r[5] or "en",
                "category": r[6] or "other",
            }
            for r in rows
        ]
        con.close()
        return results, total_count

    def mark_dead(self, url: str, ts: Optional[float] = None) -> None:
        """Blacklist a dead URL."""
        self.save_dead_pending({url: ts or time.time()})

    def is_dead(self, url: str) -> bool:
        """Check if URL is in dead blacklist."""
        dead_map = self.load_dead()
        return url in dead_map

    def get_stats(self) -> Dict[str, Any]:
        """Return database statistics."""
        if not self.db_file.exists():
            return {"active_results": 0, "dead_urls": 0, "db_size_bytes": 0}

        try:
            con = self._get_connection(read_only=True)
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM results")
            active_cnt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM dead")
            dead_cnt = cur.fetchone()[0]
            con.close()

            db_size = self.db_file.stat().st_size if self.db_file.exists() else 0
            return {
                "backend": "sqlite",
                "active_results": active_cnt,
                "dead_urls": dead_cnt,
                "db_size_bytes": db_size,
                "db_file": str(self.db_file),
                "journal_mode": "wal",
                "encryption": self.encrypt_storage,
            }
        except Exception:
            return {"backend": "sqlite", "active_results": 0, "dead_urls": 0}

    def cleanup_dead(self, cutoff_hours: float = 24.0) -> int:
        """Remove expired blacklisted dead links."""
        try:
            con = self._get_connection()
            cur = con.cursor()
            cutoff = time.time() - (cutoff_hours * 3600)
            cur.execute("DELETE FROM dead WHERE ts < ?", (cutoff,))
            deleted = cur.rowcount
            con.commit()
            con.close()
            return deleted
        except Exception:
            return 0

    def close(self) -> None:
        """Close SQLite resources."""
        pass

    # Legacy contract compatibility methods
    def get_classification_by_fp(self, fp: str) -> Optional[Tuple[str, str]]:
        if not self.db_file.exists() or not fp:
            return None
        try:
            con = self._get_connection(read_only=True)
            cur = con.cursor()
            cur.execute("SELECT lang, category FROM results WHERE fp = ? LIMIT 1", (fp,))
            row = cur.fetchone()
            con.close()
            return (row[0], row[1]) if row else None
        except Exception:
            return None

    def get_fingerprint_url(self, fp: str) -> Optional[str]:
        if not self.db_file.exists():
            return None
        try:
            con = self._get_connection(read_only=True)
            cur = con.cursor()
            cur.execute("SELECT url FROM fingerprints WHERE fp = ? LIMIT 1", (fp,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def get_btc_url(self, btc: str) -> Optional[str]:
        if not self.db_file.exists():
            return None
        try:
            con = self._get_connection(read_only=True)
            cur = con.cursor()
            cur.execute("SELECT url FROM btc_map WHERE btc = ? LIMIT 1", (btc,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def is_url_checked(self, url: str) -> bool:
        if not self.db_file.exists():
            return False
        try:
            con = self._get_connection(read_only=True)
            cur = con.cursor()
            pattern = self._get_url_mac_pattern(url)
            cur.execute(
                "SELECT 1 FROM checked WHERE url = ? OR url LIKE ? LIMIT 1",
                (url, pattern),
            )
            row = cur.fetchone()
            con.close()
            return bool(row)
        except Exception:
            return False

    def load(self) -> Optional[Dict[str, Any]]:
        if not self.db_file.exists():
            return None
        con = self._get_connection(read_only=True)
        cur = con.cursor()
        try:
            cur.execute("SELECT url,title,snippet,fp,ts,lang,category FROM results")
            results = [
                {
                    "url": r[0],
                    "title": r[1],
                    "snippet": r[2],
                    "fp": r[3],
                    "ts": r[4],
                    "lang": r[5] or "en",
                    "category": r[6] or "other",
                }
                for r in cur.fetchall()
            ]
            cur.execute("SELECT fp,url FROM fingerprints")
            seen_fp = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT btc,url FROM btc_map")
            seen_btc = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SELECT url FROM checked")
            checked_urls = [self._dec_url(r[0]) for r in cur.fetchall()]
            cur.execute("SELECT key,value FROM meta")
            meta = {}
            for k, v in cur.fetchall():
                try:
                    meta[k] = json.loads(v)
                except Exception:
                    meta[k] = v
            con.close()
            return {
                "results": results,
                "seen_fp": seen_fp,
                "seen_btc": seen_btc,
                "checked_urls": checked_urls,
                "stats": meta.get(
                    "stats", {"total": 0, "alive": 0, "clone": 0, "dead": 0, "filtered": 0}
                ),
                "queries": meta.get("queries", ""),
                "extra": meta.get("extra", ""),
                "success_count": int(meta.get("success_count", 0) or 0),
                "total_count": int(meta.get("total_count", 0) or 0),
                "total_newnym": int(meta.get("total_newnym", 0) or 0),
                "pending_queue": meta.get("pending_queue", []),
            }
        except Exception as e:
            con.close()
            raise e

    def save(self, data: Dict[str, Any], incremental: bool = False) -> None:
        con = self._get_connection()
        cur = con.cursor()
        cur.execute("BEGIN")
        for r in data.get("results", []):
            cur.execute(
                "INSERT OR REPLACE INTO results (url,title,snippet,fp,ts,lang,category) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    r["url"],
                    r.get("title", ""),
                    r.get("snippet", "")[:500],
                    r.get("fp", ""),
                    r.get("ts", time.time()),
                    r.get("lang", "en"),
                    r.get("category", "other"),
                ),
            )
        for fp, url in data.get("seen_fp", {}).items():
            cur.execute(
                "INSERT OR REPLACE INTO fingerprints (fp,url) VALUES (?,?)", (fp, url)
            )
        for btc, url in data.get("seen_btc", {}).items():
            cur.execute("INSERT OR REPLACE INTO btc_map (btc,url) VALUES (?,?)", (btc, url))
        for url in data.get("checked_urls", []):
            cur.execute(
                "INSERT OR REPLACE INTO checked (url,ts) VALUES (?,?)",
                (self._enc_url(url), time.time()),
            )
        meta_items = {
            "stats": json.dumps(data.get("stats", {})),
            "queries": data.get("queries", ""),
            "extra": data.get("extra", "")[:10000],
            "success_count": str(data.get("success_count", 0)),
            "total_count": str(data.get("total_count", 0)),
            "total_newnym": str(data.get("total_newnym", 0)),
            "pending_queue": json.dumps(data.get("pending_queue", [])),
        }
        for k, v in meta_items.items():
            cur.execute("INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)", (k, v))
        con.commit()
        dead = data.get("dead_blacklist", {})
        if dead:
            cur.execute("BEGIN")
            for url, ts in dead.items():
                cur.execute(
                    "INSERT OR REPLACE INTO dead (url,ts) VALUES (?,?)",
                    (self._enc_url(url), ts),
                )
            cur.execute("DELETE FROM dead WHERE ts < ?", (time.time() - 24 * 3600,))
            con.commit()
        con.close()

    def save_pending(self, pending: Dict[str, Any]) -> bool:
        if not pending:
            return True
        con = self._get_connection()
        cur = con.cursor()
        cur.execute("BEGIN")
        for r in pending.get("results", []):
            cur.execute(
                "INSERT OR REPLACE INTO results (url,title,snippet,fp,ts,lang,category) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    r["url"],
                    r.get("title", ""),
                    r.get("snippet", "")[:500],
                    r.get("fp", ""),
                    r.get("ts", time.time()),
                    r.get("lang", "en"),
                    r.get("category", "other"),
                ),
            )
        for fp, url in pending.get("seen_fp", {}).items():
            cur.execute(
                "INSERT OR REPLACE INTO fingerprints (fp,url) VALUES (?,?)", (fp, url)
            )
        for btc, url in pending.get("seen_btc", {}).items():
            cur.execute("INSERT OR REPLACE INTO btc_map (btc,url) VALUES (?,?)", (btc, url))
        for url in pending.get("checked_urls", []):
            cur.execute(
                "INSERT OR REPLACE INTO checked (url,ts) VALUES (?,?)",
                (self._enc_url(url), time.time()),
            )
        if "stats" in pending:
            cur.execute(
                "INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)",
                ("stats", json.dumps(pending["stats"])),
            )
        con.commit()
        con.close()
        return True

    def save_dead_pending(self, pending_dead: Dict[str, float]) -> None:
        if not pending_dead:
            return
        try:
            con = self._get_connection()
            cur = con.cursor()
            cur.execute("BEGIN")
            for url, ts in pending_dead.items():
                cur.execute(
                    "INSERT OR REPLACE INTO dead (url,ts) VALUES (?,?)",
                    (self._enc_url(url), ts),
                )
            con.commit()
            con.close()
        except Exception:
            pass

    def load_dead(self) -> Dict[str, float]:
        if not self.db_file.exists():
            return {}
        try:
            con = self._get_connection()
            cur = con.cursor()
            now = time.time()
            cutoff = now - 24 * 3600
            cur.execute("DELETE FROM dead WHERE ts < ?", (cutoff,))
            con.commit()
            cur.execute("SELECT url,ts FROM dead")
            rows = cur.fetchall()
            d = {self._dec_url(r[0]): r[1] for r in rows if now - r[1] < 24 * 3600}
            con.close()
            return d
        except Exception:
            return {}

    def save_dead(self, dead_dict: Dict[str, float]) -> None:
        self.save_dead_pending(dead_dict)

    def clear(self) -> None:
        if self.db_file.exists():
            try:
                self.db_file.unlink()
            except Exception:
                pass
        for ext in ["-wal", "-shm"]:
            sidecar = Path(str(self.db_file) + ext)
            if sidecar.exists():
                try:
                    sidecar.unlink()
                except Exception:
                    pass
        self.init_db()


# Backward Compatibility Alias
SQLiteBackend = SQLiteStorage
