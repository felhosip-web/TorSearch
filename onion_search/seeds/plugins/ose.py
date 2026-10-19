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
OnionSearchEngine Seed Plugin.
"""
from typing import Optional, Set

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.utils.helpers import OSE_SOURCES


class OSEPlugin(BaseSeedPlugin):
    """Seed plugin for OnionSearchEngine."""

    id = "ose"
    name = "OnionSearchEngine Aggregator"
    priority = 60
    timeout = 15

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        return OSE_SOURCES.get("clearnet")

    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        ep = OSE_SOURCES.get("clearnet")
        if not ep:
            return set()

        url = ep
        if query:
            url = f"{ep.split('?')[0]}?search={query}"

        resp = self._make_request(
            url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
        )
        if resp and resp.status_code == 200:
            return extract_onion_urls_from_text(resp.text)
        return set()
