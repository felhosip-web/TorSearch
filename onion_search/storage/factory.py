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
Storage Backend Factory & Registry.
Instantiates and configures BaseStorage backend instances based on settings or name.
Developed by HES Projects by FePe.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Type, Union

from onion_search.config import AppConfig, DB_FILE
from onion_search.storage.base import BaseStorage

logger = logging.getLogger("onion_search")


class StorageFactory:
    """Factory creating and registering storage backends."""

    _registry: Dict[str, Type[BaseStorage]] = {}

    @classmethod
    def register(cls, name: str, backend_cls: Type[BaseStorage]) -> None:
        """Register a storage backend class."""
        if not issubclass(backend_cls, BaseStorage):
            raise TypeError(f"Expected BaseStorage subclass, got {backend_cls}")
        cls._registry[name.lower()] = backend_cls
        logger.debug(f"[STORAGE FACTORY] Registered storage backend '{name.lower()}'")

    @classmethod
    def create(
        cls,
        backend_name: str = "sqlite",
        db_file: Union[str, Path] = DB_FILE,
        encrypt_storage: bool = False,
        **kwargs: Any,
    ) -> BaseStorage:
        """
        Instantiate a storage backend by name.
        Defaults to SQLite if backend_name is unknown.
        """
        name = backend_name.lower().strip()
        backend_cls = cls._registry.get(name)

        if not backend_cls:
            # Fallback imports if not pre-registered
            if name == "json":
                from onion_search.storage.json_backend import JSONBackend
                backend_cls = JSONBackend
            elif name == "postgres" or name == "postgresql":
                from onion_search.storage.postgres_skeleton import PostgresStorage
                backend_cls = PostgresStorage
            else:
                from onion_search.storage.sqlite_backend import SQLiteStorage
                backend_cls = SQLiteStorage

        logger.info(f"[STORAGE FACTORY] Creating storage instance for backend: '{name}'")
        try:
            return backend_cls(
                db_file=db_file,
                encrypt_storage=encrypt_storage,
                **kwargs,
            )
        except TypeError:
            # If backend constructor does not accept db_file/encrypt_storage
            return backend_cls(**kwargs)

    @classmethod
    def from_config(cls, config: AppConfig, **kwargs: Any) -> BaseStorage:
        """Create storage instance configured from AppConfig."""
        backend_name = getattr(config, "storage_backend", None) or getattr(config, "backend", "sqlite")
        encrypt_storage = getattr(config, "encrypt_storage", False)
        return cls.create(
            backend_name=backend_name,
            encrypt_storage=encrypt_storage,
            **kwargs,
        )
