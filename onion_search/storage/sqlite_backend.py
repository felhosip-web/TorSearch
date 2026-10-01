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
        con.commit()
        con.close()

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
