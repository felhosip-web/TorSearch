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
Seed Plugin Registry and Dynamic Auto-Discovery.
Maintains available seed plugins and automatically discovers plugins in
the onion_search/seeds/plugins directory.
Developed by HES Projects by FePe.
"""
import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Type

from onion_search.seeds.base import BaseSeedPlugin

logger = logging.getLogger("onion_search")


class PluginRegistry:
    """Registry managing available seed plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, BaseSeedPlugin] = {}

    def register(self, plugin: BaseSeedPlugin) -> None:
        """Register a instantiated seed plugin."""
        if not isinstance(plugin, BaseSeedPlugin):
            raise TypeError(f"Expected BaseSeedPlugin instance, got {type(plugin)}")
        self._plugins[plugin.id.lower()] = plugin
        logger.debug(f"[REGISTRY] Registered seed plugin '{plugin.id}' ({plugin.name})")

    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin by ID."""
        pid = plugin_id.lower()
        if pid in self._plugins:
            del self._plugins[pid]
            return True
        return False

    def get_plugin(self, plugin_id: str) -> Optional[BaseSeedPlugin]:
        """Retrieve a registered plugin instance by ID."""
        return self._plugins.get(plugin_id.lower())

    def get_all_plugins(self, sorted_by_priority: bool = True) -> List[BaseSeedPlugin]:
        """Return list of all registered plugins."""
        plugins = list(self._plugins.values())
        if sorted_by_priority:
            plugins.sort(key=lambda p: p.priority)
        return plugins

    def get_enabled_plugins(self, disabled_ids: Optional[List[str]] = None) -> List[BaseSeedPlugin]:
        """Return list of enabled plugins, filtering out disabled_ids."""
        disabled_set = {d.strip().lower() for d in disabled_ids} if disabled_ids else set()
        enabled = []
        for plugin in self.get_all_plugins(sorted_by_priority=True):
            if plugin.enabled and plugin.id.lower() not in disabled_set:
                enabled.append(plugin)
        return enabled

    def discover_plugins(self, plugins_package: str = "onion_search.seeds.plugins") -> None:
        """
        Dynamically discover and register all BaseSeedPlugin subclasses in the specified package directory.
        """
        try:
            mod = importlib.import_module(plugins_package)
            package_path = getattr(mod, "__file__", None)
            if not package_path:
                return

            package_dir = Path(package_path).parent
            for file_path in package_dir.glob("*.py"):
                file_name = file_path.name
                if file_name.startswith("_") or file_name == "example_plugin.py":
                    continue

                module_name = f"{plugins_package}.{file_path.stem}"
                try:
                    imported_module = importlib.import_module(module_name)
                    for _, cls in inspect.getmembers(imported_module, inspect.isclass):
                        if (
                            issubclass(cls, BaseSeedPlugin)
                            and cls is not BaseSeedPlugin
                            and getattr(cls, "id", "base_plugin") != "base_plugin"
                            and getattr(cls, "id", "example_plugin") != "example_plugin"
                        ):
                            # Instantiate and register
                            instance = cls()
                            self.register(instance)
                except Exception as e:
                    logger.warning(
                        f"[REGISTRY] Failed to load plugin module '{module_name}': {e}"
                    )
        except Exception as e:
            logger.warning(f"[REGISTRY] Plugin auto-discovery warning: {e}")


# Global Singleton Registry Instance
registry = PluginRegistry()
