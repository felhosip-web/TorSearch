"""
Storage backend module.
"""
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend

__all__ = ["JSONBackend", "SQLiteBackend"]
