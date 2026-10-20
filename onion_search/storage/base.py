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
Abstract Base Storage Interface (BaseStorage).
Defines standard strongly typed API contract for onion_search persistence backends
supporting high-throughput batch operations, pagination, search, and export.
Developed by HES Projects by FePe.
"""
from abc import ABC, abstractmethod
import csv
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class BaseStorage(ABC):
    """
    Abstract Base Storage Backend Protocol for Onion Search.
    All storage backends (SQLite, JSON, PostgreSQL, Search Engine) must implement this interface.
    """

    @abstractmethod
    def add_result(self, result: Dict[str, Any]) -> bool:
        """Insert or update a single search result record."""
        pass

    @abstractmethod
    def add_results_batch(self, results: List[Dict[str, Any]]) -> bool:
        """Insert or update a batch of search result records atomically."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def mark_dead(self, url: str, ts: Optional[float] = None) -> None:
        """Blacklist a dead or non-responsive URL."""
        pass

    @abstractmethod
    def is_dead(self, url: str) -> bool:
        """Check if URL is blacklisted in dead list."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return storage statistics (active results, dead count, storage size, etc.)."""
        pass

    @abstractmethod
    def cleanup_dead(self, cutoff_hours: float = 24.0) -> int:
        """Remove expired blacklisted dead links."""
        pass

    def cleanup_old(self, hours: float = 24.0) -> int:
        """Alias for cleanup_dead for backward compatibility."""
        return self.cleanup_dead(cutoff_hours=hours)

    def export(
        self,
        filepath: Union[str, Path],
        format: str = "csv",
        query: Optional[str] = None,
        lang: Optional[str] = None,
        category: Optional[str] = None,
    ) -> bool:
        """Export search results to file (CSV, JSON, or TXT)."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        results, _ = self.get_results(
            query=query, lang=lang, category=category, limit=100000, offset=0
        )
        if not results:
            return False

        try:
            fmt = format.lower()
            if fmt == "json":
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
            elif fmt == "txt":
                with open(p, "w", encoding="utf-8") as f:
                    for r in results:
                        f.write(
                            f"{r.get('url')} # {r.get('title','')} "
                            f"[{r.get('lang','')} {r.get('category','')}]\n"
                        )
            else:  # csv
                with open(p, "w", encoding="utf-8", newline="") as f:
                    fields = ["url", "title", "snippet", "fp", "ts", "lang", "category"]
                    writer = csv.DictWriter(f, fieldnames=fields)
                    writer.writeheader()
                    for r in results:
                        writer.writerow({
                            "url": r.get("url", ""),
                            "title": r.get("title", ""),
                            "snippet": r.get("snippet", ""),
                            "fp": r.get("fp", ""),
                            "ts": r.get("ts", time.time()),
                            "lang": r.get("lang", "en"),
                            "category": r.get("category", "other"),
                        })
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close connections or release storage resources."""
        pass

    def __enter__(self) -> "BaseStorage":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # Legacy Compatibility Contract Methods
    @abstractmethod
    def load(self) -> Optional[Dict[str, Any]]:
        """Load full application state for legacy caller compatibility."""
        pass

    @abstractmethod
    def save(self, data: Dict[str, Any], incremental: bool = False) -> None:
        """Save full application state for legacy caller compatibility."""
        pass

    @abstractmethod
    def save_pending(self, pending: Dict[str, Any]) -> bool:
        """Save incremental delta state."""
        pass

    @abstractmethod
    def load_dead(self) -> Dict[str, float]:
        """Load dead blacklist map."""
        pass

    @abstractmethod
    def save_dead(self, dead_dict: Dict[str, float]) -> None:
        """Save dead blacklist map."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Purge all stored data."""
        pass
