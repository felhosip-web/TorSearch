"""
SQLite storage backend.
"""
import json
import sqlite3
import time
from onion_search.utils.helpers import DB_FILE


class SQLiteBackend:
    """SQLite persistence backend for search results, fingerprints, and state."""

    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        con = sqlite3.connect(self.db_file)
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
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

        # Secondary indexes for fast filtering and lookups
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_ts ON results(ts DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_lang ON results(lang)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_cat ON results(category)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_fp ON results(fp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_checked_url ON checked(url)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dead_ts ON dead(ts)")

        con.commit()
        con.close()

    def get_classification_by_fp(self, fp):
        """Query database for previously computed (lang, category) by content fingerprint."""
        if not self.db_file.exists() or not fp:
            return None
        try:
            con = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT lang, category FROM results WHERE fp = ? LIMIT 1", (fp,))
            row = cur.fetchone()
            con.close()
            return (row[0], row[1]) if row else None
        except Exception:
            return None

    def get_fingerprint_url(self, fp):
        """Query database directly for an existing duplicate content fingerprint."""
        if not self.db_file.exists():
            return None
        try:
            con = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT url FROM fingerprints WHERE fp = ? LIMIT 1", (fp,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def get_btc_url(self, btc):
        """Query database directly for an existing Bitcoin address mapping."""
        if not self.db_file.exists():
            return None
        try:
            con = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT url FROM btc_map WHERE btc = ? LIMIT 1", (btc,))
            row = cur.fetchone()
            con.close()
            return row[0] if row else None
        except Exception:
            return None

    def is_url_checked(self, url):
        """Check if URL was already checked previously in the database."""
        if not self.db_file.exists():
            return False
        try:
            con = sqlite3.connect(f"file:{self.db_file}?mode=ro", uri=True)
            cur = con.cursor()
            cur.execute("SELECT 1 FROM checked WHERE url = ? LIMIT 1", (url,))
            row = cur.fetchone()
            con.close()
            return bool(row)
        except Exception:
            return False

    def load(self):
        if not self.db_file.exists():
            return None
        con = sqlite3.connect(self.db_file)
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
            checked_urls = [r[0] for r in cur.fetchall()]
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

    def save(self, data, incremental=False):
        con = sqlite3.connect(self.db_file)
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
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
                "INSERT OR REPLACE INTO checked (url,ts) VALUES (?,?)", (url, time.time())
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
                cur.execute("INSERT OR REPLACE INTO dead (url,ts) VALUES (?,?)", (url, ts))
            # takaritas
            cur.execute("DELETE FROM dead WHERE ts < ?", (time.time() - 24 * 3600,))
            con.commit()
        con.close()

    def save_pending(self, pending):
        if not pending:
            return True
        con = sqlite3.connect(self.db_file)
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
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
                "INSERT OR REPLACE INTO checked (url,ts) VALUES (?,?)", (url, time.time())
            )
        if "stats" in pending:
            cur.execute(
                "INSERT OR REPLACE INTO meta (key,value) VALUES (?,?)",
                ("stats", json.dumps(pending["stats"])),
            )
        con.commit()
        con.close()
        return True

    def save_dead_pending(self, pending_dead):
        if not pending_dead:
            return
        try:
            con = sqlite3.connect(self.db_file)
            cur = con.cursor()
            cur.execute("BEGIN")
            for url, ts in pending_dead.items():
                cur.execute("INSERT OR REPLACE INTO dead (url,ts) VALUES (?,?)", (url, ts))
            cur.execute("DELETE FROM dead WHERE ts < ?", (time.time() - 24 * 3600,))
            con.commit()
            con.close()
        except Exception:
            pass

    def load_dead(self):
        con = sqlite3.connect(self.db_file)
        cur = con.cursor()
        try:
            now = time.time()
            cutoff = now - 24 * 3600
            cur.execute("DELETE FROM dead WHERE ts < ?", (cutoff,))
            con.commit()
            cur.execute("SELECT url,ts FROM dead")
            rows = cur.fetchall()
            d = {r[0]: r[1] for r in rows if now - r[1] < 24 * 3600}
            con.close()
            return d
        except Exception:
            try:
                con.close()
            except Exception:
                pass
            return {}

    def save_dead(self, dead_dict):
        self.save_dead_pending(dead_dict)

    def cleanup_dead(self):
        try:
            con = sqlite3.connect(self.db_file)
            cur = con.cursor()
            cutoff = time.time() - 24 * 3600
            cur.execute("DELETE FROM dead WHERE ts < ?", (cutoff,))
            con.commit()
            con.close()
        except Exception:
            pass

    def clear(self):
        if self.db_file.exists():
            self.db_file.unlink()
        self.init_db()
