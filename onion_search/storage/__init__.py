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
Storage Layer Package for Onion Kereső.
Provides abstract BaseStorage protocol, SQLiteStorage, JSONBackend, PostgresStorage skeleton, and StorageFactory.
"""
from onion_search.storage.base import BaseStorage
from onion_search.storage.crypto import StorageEncryptor
from onion_search.storage.factory import StorageFactory
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.postgres_skeleton import PostgresStorage
from onion_search.storage.sqlite_backend import SQLiteBackend, SQLiteStorage

# Register standard backends with factory
StorageFactory.register("sqlite", SQLiteStorage)
StorageFactory.register("json", JSONBackend)
StorageFactory.register("postgres", PostgresStorage)
StorageFactory.register("postgresql", PostgresStorage)

__all__ = [
    "BaseStorage",
    "SQLiteStorage",
    "SQLiteBackend",
    "JSONBackend",
    "PostgresStorage",
    "StorageEncryptor",
    "StorageFactory",
]
