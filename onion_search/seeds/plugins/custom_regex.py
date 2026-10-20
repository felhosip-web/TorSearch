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
Generic User Custom URL + Regex / CSS Selector Seed Plugin.
Allows adding user-defined custom seed URLs with custom extraction rules.
"""
import re
from typing import Optional, Set

from bs4 import BeautifulSoup
from onion_search.seeds.base import BaseSeedPlugin, extract_onion_urls_from_text
from onion_search.utils.helpers import normalize_onion_url


class CustomUrlRegexPlugin(BaseSeedPlugin):
    """
    Generic configurable seed plugin that fetches from custom URL(s)
    and parses .onion URLs using regex or CSS selector.
    """

    id = "custom_regex"
    name = "Egyéni URL + Regex / CSS Szűrő Forrás"
    priority = 100
    timeout = 15

    def __init__(
        self,
        target_url: Optional[str] = None,
        custom_regex: Optional[str] = None,
        css_selector: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.target_url = target_url
        self.custom_regex = re.compile(custom_regex, re.IGNORECASE) if custom_regex else None
        self.css_selector = css_selector

    def get_primary_endpoint(
        self, proxy_url: Optional[str] = None, allow_clearnet: bool = False
    ) -> Optional[str]:
        return self.target_url

    def _do_fetch_seeds(
        self,
        query: Optional[str] = None,
        proxy_url: Optional[str] = None,
        allow_clearnet: bool = False,
        timeout: int = 15,
    ) -> Set[str]:
        if not self.target_url:
            return set()

        url = self.target_url
        if query and "{query}" in url:
            url = url.format(query=query)

        resp = self._make_request(
            url, proxy_url=proxy_url, allow_clearnet=allow_clearnet, timeout=timeout
        )
        if not resp or resp.status_code != 200:
            return set()

        text = resp.text
        found: Set[str] = set()

        if self.css_selector:
            try:
                soup = BeautifulSoup(text, "html.parser")
                elements = soup.select(self.css_selector)
                for el in elements:
                    href = el.get("href") or el.get_text()
                    urls = extract_onion_urls_from_text(href)
                    found.update(urls)
            except Exception:
                pass

        if self.custom_regex:
            for match in self.custom_regex.finditer(text):
                raw = match.group(0)
                norm = normalize_onion_url(raw)
                if norm:
                    found.add(norm)

        # Fallback to standard onion regex extraction if custom rules yielded nothing
        if not found:
            found = extract_onion_urls_from_text(text)

        return found
