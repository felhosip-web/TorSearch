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
Tests for Apache License 2.0 compliance, author attribution, and license dialog.
"""
import json
from pathlib import Path
import tkinter as tk

from onion_search import __author__, __license__
from onion_search.config import APP_AUTHOR, APP_COPYRIGHT, APP_LICENSE
from onion_search.ui.main_window import MainWindow


def test_license_files_presence_and_content():
    repo_root = Path(__file__).resolve().parent.parent

    # 1. LICENSE file check
    license_file = repo_root / "LICENSE"
    assert license_file.exists(), "LICENSE file must exist"
    license_content = license_file.read_text(encoding="utf-8")
    assert "Apache License" in license_content
    assert "Version 2.0, January 2004" in license_content
    assert "Copyright 2026 HES Projects by FePe" in license_content

    # 2. NOTICE file check
    notice_file = repo_root / "NOTICE"
    assert notice_file.exists(), "NOTICE file must exist"
    notice_content = notice_file.read_text(encoding="utf-8")
    assert "HES Projects by FePe" in notice_content
    assert "Apache License, Version 2.0" in notice_content

    # 3. package.json check
    pkg_file = repo_root / "package.json"
    assert pkg_file.exists()
    pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
    assert pkg_data.get("license") == "Apache-2.0"
    assert pkg_data.get("author") == "HES Projects by FePe"


def test_python_metadata_attribution():
    assert APP_AUTHOR == "HES Projects by FePe"
    assert APP_LICENSE == "Apache-2.0"
    assert "HES Projects by FePe" in APP_COPYRIGHT
    assert __author__ == "HES Projects by FePe"
    assert __license__ == "Apache-2.0"


def test_about_license_dialog():
    root = tk.Tk()
    root.withdraw()
    app = MainWindow(root)

    # Window title attribution check
    assert "HES Projects by FePe" in root.title()
    assert "Apache" in root.title()

    # Open about dialog
    app.open_about_dialog()
    root.update()

    toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(toplevels) >= 1
    dlg = toplevels[-1]
    assert "HES Projects by FePe" in dlg.title()
    assert "Apache" in dlg.title()

    dlg.destroy()
    root.destroy()
