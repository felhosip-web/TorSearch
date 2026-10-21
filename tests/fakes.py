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
Reusable test fakes for async HTTP client streaming and mock testing.
"""
from typing import Dict, List, Optional, Union


class FakeStreamResponse:
    """Async context manager mocking a streaming response from httpx.AsyncClient.stream()."""

    def __init__(
        self,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        content_chunks: Optional[List[bytes]] = None,
        url: str = "http://testonion1234567890abcdef.onion",
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.url = url
        self.content_chunks = content_chunks or [
            b"<html><head><title>Test Onion Page</title></head><body>"
            + b"Content for testing onion page " * 20
            + b"</body></html>"
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def aiter_bytes(self):
        for chunk in self.content_chunks:
            yield chunk


class FakeAsyncClient:
    """Reusable fake client supporting stream() for async_fetch_page_httpx tests."""

    def __init__(self, responses: Optional[Union[FakeStreamResponse, List[FakeStreamResponse]]] = None):
        if responses is None:
            self.responses = [FakeStreamResponse()]
        elif isinstance(responses, FakeStreamResponse):
            self.responses = [responses]
        else:
            self.responses = list(responses)
        self.calls = []

    def stream(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, follow_redirects: bool = False):
        self.calls.append({"method": method, "url": url, "headers": headers, "follow_redirects": follow_redirects})
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)
