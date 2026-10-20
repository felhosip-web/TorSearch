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
Seed Orchestrator coordinating plugin execution, priority fallback cascades,
health-check pre-filtering, and detailed logging.
Developed by HES Projects by FePe.
"""
import logging
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from onion_search.seeds.base import BaseSeedPlugin
from onion_search.seeds.registry import PluginRegistry, registry as default_registry
from onion_search.utils.helpers import MIN_SEED_YIELD_THRESHOLD

logger = logging.getLogger("onion_search")


class SeedOrchestrator:
    """
    Coordinates seed collection across registered plugins using priority cascade fallback.
    """

    def __init__(self, plugin_registry: Optional[PluginRegistry] = None) -> None:
        self.registry = plugin_registry or default_registry
        # Auto-discover plugins if none registered yet
        if not self.registry.get_all_plugins():
            self.registry.discover_plugins()

    def run_health_checks(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        force: bool = False,
    ) -> Dict[str, Tuple[bool, str]]:
        """Run health check for all enabled plugins."""
        results: Dict[str, Tuple[bool, str]] = {}
        for plugin in self.registry.get_enabled_plugins():
            status = plugin.health_check(
                proxy_url=proxy_url, allow_clearnet=allow_clearnet, force=force
            )
            results[plugin.id] = status
            logger.info(
                f"[SEED HEALTH] Plugin '{plugin.id}' ({plugin.name}): "
                f"{'🟢 OK' if status[0] else '🔴 HIBA'} - {status[1]}"
            )
        return results

    def fetch_all(
        self,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        selected_sources: Optional[List[str]] = None,
        use_only_healthy: bool = False,
        min_yield_threshold: int = MIN_SEED_YIELD_THRESHOLD,
        target_total_seeds: Optional[int] = None,
        query: Optional[str] = None,
        on_source_progress: Optional[Callable[[str, int], None]] = None,
        source_dispatch: Optional[Dict[str, Callable[[], Set[str]]]] = None,
    ) -> Tuple[Set[str], Dict[str, int]]:
        """
        Query plugins in priority fallback cascade sequence.
        """
        enabled_plugins = self.registry.get_enabled_plugins()

        # Filter by selected_sources if provided
        if selected_sources:
            norm_selected = [s.strip().lower() for s in selected_sources]
            candidates = [p for p in enabled_plugins if p.id.lower() in norm_selected]
            # Add any sources present in selected_sources that might not be in enabled_plugins if custom
            existing_ids = {p.id.lower() for p in candidates}
            for s_id in norm_selected:
                if s_id not in existing_ids and source_dispatch and s_id in source_dispatch:
                    # Create dummy plugin wrapper for legacy/custom dispatch
                    class DummyPlugin(BaseSeedPlugin):
                        id = s_id
                        name = s_id.upper()
                        priority = 99
                        def _do_fetch_seeds(self, **kwargs): return set()
                    candidates.append(DummyPlugin())
        else:
            candidates = list(enabled_plugins)

        # Sort candidates strictly by plugin.priority
        candidates.sort(key=lambda p: p.priority)

        source_counts: Dict[str, int] = {}
        all_found: Set[str] = set()

        cand_names = ", ".join([p.id.upper() for p in candidates])
        logger.info(
            f"[SEED ORCHESTRATOR] Maggyűjtés indítása prioritási láncban: [{cand_names}] "
            f"(Min. hozamküszöb: {min_yield_threshold} mag/forrás, csak egészséges: {use_only_healthy})"
        )

        for plugin in candidates:
            pid = plugin.id.lower()

            # If use_only_healthy mode is enabled, pre-check plugin health
            if use_only_healthy:
                is_healthy, health_msg = plugin.health_check(
                    proxy_url=proxy_url, allow_clearnet=allow_clearnet
                )
                if not is_healthy:
                    logger.warning(
                        f"[SEED HEALTH-SKIP] Plugin '{plugin.id.upper()}' kihagyva, "
                        f"mert nem egészséges ({health_msg})."
                    )
                    source_counts[plugin.id] = 0
                    if on_source_progress:
                        on_source_progress(plugin.id, 0)
                    continue

            logger.info(f"[SEED ORCHESTRATOR] Plugin lekérdezése: {plugin.id.upper()}...")
            try:
                if source_dispatch and pid in source_dispatch:
                    seeds = source_dispatch[pid]()
                else:
                    seeds = plugin.fetch_seeds(
                        query=query,
                        proxy_url=proxy_url,
                        allow_clearnet=allow_clearnet,
                    )
                count = len(seeds)
                source_counts[plugin.id] = count
                all_found.update(seeds)

                if on_source_progress:
                    on_source_progress(plugin.id, count)

                if count < min_yield_threshold:
                    logger.warning(
                        f"[SEED FALLBACK] {plugin.id.upper()} alacsony hozam ({count} < {min_yield_threshold} mag). "
                        f"Kaszkád fallback léptetés a következő forrásra..."
                    )
                else:
                    logger.info(
                        f"[SEED ORCHESTRATOR] {plugin.id.upper()}: sikeres hozam ({count} mag)"
                    )

                if target_total_seeds is not None and len(all_found) >= target_total_seeds:
                    logger.info(
                        f"[SEED ORCHESTRATOR] Cél hozam elérve ({len(all_found)} >= {target_total_seeds}), "
                        f"további fallback források lekérdezése nem szükséges."
                    )
                    break

            except Exception as e:
                logger.error(
                    f"[SEED ORCHESTRATOR ERROR] Hiba a(z) {plugin.id} plugin futtatásakor: {e}. Fallback aktiválva."
                )
                source_counts[plugin.id] = 0
                if on_source_progress:
                    on_source_progress(plugin.id, 0)

        return all_found, source_counts
