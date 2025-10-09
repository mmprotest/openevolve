"""OpenAI compatible chat completion helper."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Iterable, Protocol, Sequence

import httpx

from .config import OpenEvolveSettings, load_settings
from .utils import ensure_event_loop

DiffValidator = Callable[[str], bool]


class LLMClientProtocol(Protocol):
    """Typed protocol implemented by language model clients."""

    async def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> "GenerationResult":
        """Return candidate diff patches for the supplied prompt."""

    async def aclose(self) -> None:
        """Close any underlying network resources."""


@dataclass
class GenerationResult:
    """Container for a batch of generated diff candidates."""

    candidates: list[str]
    raw_response: dict[str, Any] | None = None


class OpenEvolveClient(LLMClientProtocol):
    """Client for interacting with OpenAI compatible chat completion APIs."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        diff_validator: DiffValidator | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings: OpenEvolveSettings = load_settings()
        self._api_key = api_key if api_key is not None else settings.openai_api_key
        self._base_url = base_url if base_url is not None else settings.openai_base_url
        self._default_model = default_model or settings.model_primary
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._diff_validator = diff_validator
        self._client = client
        self._client_owner = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(base_url=self._base_url, headers=headers, timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client and self._client_owner:
            await self._client.aclose()
        self._client = None

    async def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Request diff suggestions from the language model."""

        if n < 1:
            raise ValueError("Parameter 'n' must be at least 1")

        payload_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        if extra_messages:
            payload_messages.extend(extra_messages)

        payload: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": payload_messages,
            "n": n,
            "temperature": temperature,
        }

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                candidates = self._extract_candidates(data)
                return GenerationResult(candidates=candidates, raw_response=data)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(min(2 ** attempt, 10))
        raise RuntimeError("Failed to generate completions") from last_error

    def _extract_candidates(self, payload: dict[str, Any]) -> list[str]:
        choices = payload.get("choices")
        if not isinstance(choices, Iterable):
            raise ValueError("Invalid response format: missing choices")

        candidates: list[str] = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message", {})
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                if self._diff_validator is None or self._diff_validator(content):
                    candidates.append(content.strip())
        if not candidates:
            raise ValueError("No valid diff candidates returned by model")
        return candidates

    def generate_sync(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Convenience wrapper that runs :meth:`generate` in the current event loop."""

        loop = ensure_event_loop()
        return loop.run_until_complete(
            self.generate(
                prompt=prompt,
                system=system,
                model=model,
                n=n,
                temperature=temperature,
                extra_messages=extra_messages,
            )
        )

    async def __aenter__(self) -> "OpenEvolveClient":
        await self._get_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


def build_default_client(diff_validator: DiffValidator | None = None) -> OpenEvolveClient:
    """Create a client configured with global settings."""

    settings = load_settings()
    return OpenEvolveClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        default_model=settings.model_primary,
        diff_validator=diff_validator,
    )
