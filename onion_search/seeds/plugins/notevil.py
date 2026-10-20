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
not Evil Search Engine Seed Plugin.
"""
from typing import Optional, Set

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.utils.helpers import NOTEVIL_SOURCES


class NotEvilPlugin(BaseSeedPlugin):
    """Seed plugin for not Evil search engine (last resort fallback)."""

    id = "notevil"
    name = "not Evil Search Engine"
    priority = 80
    timeout = 15

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        if proxy_url:
            return NOTEVIL_SOURCES["onion"]
        if allow_clearnet:
            return NOTEVIL_SOURCES["clearnet"]
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
            endpoints.append(NOTEVIL_SOURCES["onion"])
        if allow_clearnet or proxy_url:
            endpoints.append(NOTEVIL_SOURCES["clearnet"])

        found: Set[str] = set()
        for ep in endpoints:
            url = ep
            if query:
                url = f"{ep.split('?')[0]}?q={query}"
            resp = self._make_request(
                url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
            )
            if resp and resp.status_code == 200:
                urls = extract_onion_urls_from_text(resp.text)
                found.update(urls)
                if len(found) >= 10:
                    break
        return found
