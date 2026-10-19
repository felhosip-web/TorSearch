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
GitHub Curated Lists Seed Plugin.
"""
from typing import Optional, Set

from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.utils.helpers import GITHUB_SOURCES


class GitHubPlugin(BaseSeedPlugin):
    """Seed plugin for curated GitHub repositories."""

    id = "github"
    name = "GitHub Curated Onion Lists"
    priority = 50
    timeout = 15

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        if GITHUB_SOURCES:
            return GITHUB_SOURCES[0]
        return None

    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        found: Set[str] = set()
        for src in GITHUB_SOURCES:
            resp = self._make_request(
                src, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
            )
            if resp and resp.status_code == 200:
                found.update(extract_onion_urls_from_text(resp.text))
        return found
