"""Lightweight fallback implementation of the httpx API used in tests."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


class HTTPStatusError(RuntimeError):
    pass


class Request:
    def __init__(self, method: str, url: str, *, json: Any | None = None, headers: dict[str, str] | None = None) -> None:
        self.method = method
        self.url = url
        self._json = json
        self.headers = headers or {}

    def json(self) -> Any | None:
        return self._json


class Response:
    def __init__(self, status_code: int, *, json: Any | None = None, text: str | None = None) -> None:
        self.status_code = status_code
        self._json = json
        self.text = text or ""

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if 400 <= self.status_code:
            raise HTTPStatusError(f"Request failed with status {self.status_code}")


class MockTransport:
    def __init__(self, handler: Callable[[Request], Response | Awaitable[Response]]) -> None:
        self._handler = handler

    async def handle_async_request(self, request: Request) -> Response:
        result = self._handler(request)
        if asyncio.iscoroutine(result):
            result = await result
        return result


class AsyncClient:
    def __init__(
        self,
        *,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        transport: MockTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._transport = transport
        self._closed = False

    async def post(self, url: str, *, json: Any | None = None) -> Response:
        if self._transport is None:
            raise RuntimeError("Mock httpx client cannot perform real HTTP requests")
        request = Request("POST", self._full_url(url), json=json, headers=self.headers)
        return await self._transport.handle_async_request(request)

    def _full_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    async def aclose(self) -> None:
        self._closed = True

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.aclose()
