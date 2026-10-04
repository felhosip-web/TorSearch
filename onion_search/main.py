#!/usr/bin/env python3
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
Application entry point and dependency wiring for Onion Search.
Developed by HES Projects by FePe.
"""
import sys
from pathlib import Path

# Allow direct script execution without PYTHONPATH adjustment
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
from onion_search.core.detector import ContentDetector
from onion_search.core.fetcher import OnionFetcher, SessionManager
from onion_search.core.neonym import TorController
from onion_search.storage.json_backend import JSONBackend
from onion_search.storage.sqlite_backend import SQLiteBackend
from onion_search.ui.main_window import MainWindow


def create_app(root=None):
    """Bootstrap application components, wire dependencies, and return the initialized window."""
    if root is None:
        root = tk.Tk()

    # 1. Initialize persistence backends
    sqlite_backend = SQLiteBackend()
    json_backend = JSONBackend()

    # 2. Initialize domain core components
    detector = ContentDetector()
    session_manager = SessionManager()
    fetcher = OnionFetcher(session_manager=session_manager, detector=detector)
    tor_controller = TorController(on_sessions_reset=session_manager.close_all)

    # 3. Wire components into the UI main window
    app = MainWindow(
        root=root,
        fetcher=fetcher,
        detector=detector,
        tor_controller=tor_controller,
        sqlite_backend=sqlite_backend,
        json_backend=json_backend,
    )
    return root, app


def main():
    """Application main entry point."""
    root, _ = create_app()
    root.mainloop()


if __name__ == "__main__":
    main()
