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
JSON storage backend implementing BaseStorage abstract protocol with optional Fernet encryption.
Developed by HES Projects by FePe.
"""
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from onion_search.storage.base import BaseStorage
from onion_search.storage.crypto import StorageEncryptor
from onion_search.utils.helpers import DEAD_FILE, STATE_FILE


class JSONBackend(BaseStorage):
    """JSON file persistence backend implementing BaseStorage protocol."""

    def __init__(
        self,
        state_file: Union[str, Path] = STATE_FILE,
        dead_file: Union[str, Path] = DEAD_FILE,
        encrypt_storage: bool = False,
        encryptor: Optional[StorageEncryptor] = None,
        **kwargs: Any,
    ) -> None:
        self.state_file = Path(state_file)
        self.dead_file = Path(dead_file)
        self.encrypt_storage = encrypt_storage
        self.encryptor = encryptor or (StorageEncryptor() if encrypt_storage else None)

    def add_result(self, result: Dict[str, Any]) -> bool:
        return self.add_results_batch([result])

    def add_results_batch(self, results: List[Dict[str, Any]]) -> bool:
        data = self.load() or {"results": []}
        data_results = data.get("results", [])
        existing_urls = {r.get("url") for r in data_results}
        for r in results:
            if r.get("url") not in existing_urls:
                data_results.append(r)
                existing_urls.add(r.get("url"))
        data["results"] = data_results
        self.save(data)
        return True

    def get_results(
        self,
        query: Optional[str] = None,
        lang: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        data = self.load() or {}
        results = data.get("results", [])
        if lang and lang != "all":
            results = [r for r in results if r.get("lang") == lang]
        if category and category != "all":
            results = [r for r in results if r.get("category") == category]
        if query:
            q_lower = query.lower()
            results = [
                r for r in results
                if q_lower in r.get("title", "").lower() or q_lower in r.get("snippet", "").lower()
            ]
        total = len(results)
        paginated = results[offset : offset + limit]
        return paginated, total

    def mark_dead(self, url: str, ts: Optional[float] = None) -> None:
        dead = self.load_dead()
        dead[url] = ts or time.time()
        self.save_dead(dead)

    def is_dead(self, url: str) -> bool:
        dead = self.load_dead()
        return url in dead

    def get_stats(self) -> Dict[str, Any]:
        data = self.load() or {}
        results = data.get("results", [])
        dead = self.load_dead()
        size = self.state_file.stat().st_size if self.state_file.exists() else 0
        return {
            "backend": "json",
            "active_results": len(results),
            "dead_urls": len(dead),
            "db_size_bytes": size,
            "encryption": self.encrypt_storage,
        }

    def cleanup_dead(self, cutoff_hours: float = 24.0) -> int:
        dead = self.load_dead()
        now = time.time()
        cutoff = now - (cutoff_hours * 3600)
        filtered = {u: t for u, t in dead.items() if t >= cutoff}
        cleaned_cnt = len(dead) - len(filtered)
        self.save_dead(filtered)
        return cleaned_cnt

    def load(self) -> Optional[Dict[str, Any]]:
        if not self.state_file.exists():
            return None
        try:
            with open(self.state_file, "rb") as f:
                raw = f.read()
            if self.encryptor:
                try:
                    return self.encryptor.decrypt_json(raw)
                except Exception:
                    pass
            # Fallback to plain JSON decoding
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return None

    def save(self, data: Dict[str, Any], incremental: bool = False) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if self.encrypt_storage and self.encryptor:
            encrypted_data = self.encryptor.encrypt_json(data)
            with open(self.state_file, "wb") as f:
                f.write(encrypted_data)
        else:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def save_pending(self, pending: Dict[str, Any]) -> bool:
        return False

    def load_dead(self) -> Dict[str, float]:
        if not self.dead_file.exists():
            return {}
        try:
            with open(self.dead_file, "rb") as f:
                raw = f.read()
            if self.encryptor:
                try:
                    d = self.encryptor.decrypt_json(raw)
                except Exception:
                    d = json.loads(raw.decode("utf-8"))
            else:
                d = json.loads(raw.decode("utf-8"))
            now = time.time()
            return {u: t for u, t in d.items() if now - t < 24 * 3600}
        except Exception:
            return {}

    def save_dead(self, dead_dict: Dict[str, float]) -> None:
        try:
            self.dead_file.parent.mkdir(parents=True, exist_ok=True)
            if self.encrypt_storage and self.encryptor:
                encrypted = self.encryptor.encrypt_json(dead_dict)
                with open(self.dead_file, "wb") as f:
                    f.write(encrypted)
            else:
                with open(self.dead_file, "w", encoding="utf-8") as f:
                    json.dump(dead_dict, f)
        except Exception:
            pass

    def save_dead_pending(self, pending_dead: Dict[str, float]) -> None:
        self.save_dead(pending_dead)

    def clear(self) -> None:
        for p in [self.state_file, self.dead_file]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
