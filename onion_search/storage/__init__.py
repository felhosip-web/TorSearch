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
Storage backend module.
Developed by HES Projects by FePe.
"""
from onion_search.storage.crypto import StorageEncryptor
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend

__all__ = ["StorageEncryptor", "JSONBackend", "SQLiteBackend"]
