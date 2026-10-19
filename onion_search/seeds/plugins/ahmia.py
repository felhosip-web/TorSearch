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
Ahmia Index Seed Plugin.
"""
from typing import Optional, Set

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.utils.helpers import AHMIA_SOURCES


class AhmiaPlugin(BaseSeedPlugin):
    """Seed plugin for Ahmia index."""

    id = "ahmia"
    name = "Ahmia Onion Index"
    priority = 90
    timeout = 15

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        if proxy_url:
            return AHMIA_SOURCES["onion"]
        if allow_clearnet:
            return AHMIA_SOURCES["clearnet"]
        return None

    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        endpoints = []
        if proxy_url:
            endpoints.append(AHMIA_SOURCES["onion"])
        if allow_clearnet or proxy_url:
            endpoints.append(AHMIA_SOURCES["clearnet"])

        for ep in endpoints:
            resp = self._make_request(
                ep, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
            )
            if resp and resp.status_code == 200:
                return extract_onion_urls_from_text(resp.text)
        return set()
