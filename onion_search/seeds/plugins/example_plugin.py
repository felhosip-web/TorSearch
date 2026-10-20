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
EXAMPLE / TEMPLATE SEED PLUGIN FOR DEVELOPERS.
==============================================
How to create a new seed source plugin:
1. Inherit from `BaseSeedPlugin`.
2. Define unique `id` (e.g., 'my_custom_source'), human-readable `name`, and `priority` (1-100).
3. Implement `_do_fetch_seeds(query, proxy_url, allow_clearnet, timeout)` returning a set of .onion URLs.
4. Optionally override `_do_health_check()` or `get_primary_endpoint()`.
5. Save this file in `onion_search/seeds/plugins/my_custom_source.py`.
   It will be automatically discovered and loaded by `PluginRegistry`!
"""
from typing import Optional, Set

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text


class ExampleSeedPlugin(BaseSeedPlugin):
    """
    Template example seed plugin.
    Rename and adapt this class when adding a new seed provider.
    """

    id = "example_plugin"  # Unique string ID
    name = "Példa Magforrás Plugin"  # Human readable title
    priority = 100  # Priority in cascade execution (10 = highest, 100 = lowest)
    enabled = False  # Disabled by default template
    timeout = 15

    # Example endpoint URLs
    PRIMARY_ONION = "http://example1234567890abcdefghijklmnopqrstuvwxyz234567.onion/fresh"
    PRIMARY_CLEARNET = "https://example-mirror.net/fresh"

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        if proxy_url:
            return self.PRIMARY_ONION
        if allow_clearnet:
            return self.PRIMARY_CLEARNET
        return None

    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        endpoint = self.get_primary_endpoint(proxy_url=proxy_url, allow_clearnet=allow_clearnet)
        if not endpoint:
            return set()

        # Execute HTTP GET request using BaseSeedPlugin's secure proxy helper
        resp = self._make_request(
            endpoint, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
        )

        if resp and resp.status_code == 200:
            # Extract and normalize all valid .onion URLs from response body
            return extract_onion_urls_from_text(resp.text)

        return set()
