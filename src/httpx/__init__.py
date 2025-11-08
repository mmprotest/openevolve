"""Lightweight fallback implementation of the httpx API used in tests.

This module mirrors a tiny portion of the :mod:`httpx` surface area so the
project can run its unit tests without depending on the real third-party
package.  The original implementation deliberately raised an exception when a
consumer attempted to perform a real network request without providing a mock
transport.  That behaviour prevented the example scripts from running in user
environments where a live language model request is expected.

To make the fallback usable outside of tests we provide a very small HTTP
implementation backed by :mod:`urllib.request`.  It is intentionally minimal –
only the ``post`` method is implemented – but that is sufficient for the
``OpenEvolveClient`` which exclusively issues POST requests to the chat
completions endpoint.  When a mock transport is supplied we continue to follow
the previous behaviour so existing tests remain untouched.
"""

from __future__ import annotations

import asyncio
import json as json_module
from typing import Any, Awaitable, Callable
from urllib import error as urllib_error
from urllib import request as urllib_request


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
        request = Request("POST", self._full_url(url), json=json, headers=self.headers)
        if self._transport is not None:
            return await self._transport.handle_async_request(request)

        return await asyncio.to_thread(self._perform_http_request, request)

    def _full_url(self, path: str) -> str:
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _perform_http_request(self, request: Request) -> Response:
        data: bytes | None = None
        headers = dict(request.headers)
        if request._json is not None:
            data = json_module.dumps(request._json).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")

        http_request = urllib_request.Request(
            request.url,
            data=data,
            headers=headers,
            method=request.method,
        )

        try:
            with urllib_request.urlopen(http_request, timeout=self.timeout) as response:  # noqa: S310
                payload = response.read()
                text = payload.decode("utf-8", errors="replace")
                try:
                    json_payload = json_module.loads(text) if text else None
                except json_module.JSONDecodeError:
                    json_payload = None
                status_code = response.getcode() or 0
                return Response(status_code, json=json_payload, text=text)
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            return Response(getattr(exc, "code", 0) or 0, json=None, text=body)
        except urllib_error.URLError as exc:  # pragma: no cover - network failures are unexpected
            raise RuntimeError("HTTP request failed") from exc

    async def aclose(self) -> None:
        self._closed = True

    async def __aenter__(self) -> "AsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.aclose()
