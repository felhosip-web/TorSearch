"""
JSON storage backend.
"""
import json
import time
from onion_search.utils.helpers import STATE_FILE, DEAD_FILE


class JSONBackend:
    """JSON file persistence backend."""

    def __init__(self, state_file=STATE_FILE, dead_file=DEAD_FILE):
        self.state_file = state_file
        self.dead_file = dead_file

    def load(self):
        if not self.state_file.exists():
            return None
        with open(self.state_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, data, incremental=False):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_pending(self, pending):
        return False

    def load_dead(self):
        if not self.dead_file.exists():
            return {}
        try:
            with open(self.dead_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            now = time.time()
            return {u: t for u, t in d.items() if now - t < 24 * 3600}
        except Exception:
            return {}

    def save_dead(self, dead_dict):
        try:
            with open(self.dead_file, "w", encoding="utf-8") as f:
                json.dump(dead_dict, f)
        except Exception:
            pass

    def save_dead_pending(self, pending_dead):
        self.save_dead(pending_dead)

    def clear(self):
        for p in [self.state_file, self.dead_file]:
            if p.exists():
                p.unlink()
