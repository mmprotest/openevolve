"""Utility helpers."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Iterator


def ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Return a running event loop or create a new one for the current thread."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@contextmanager
def temp_override(mapping: dict[str, Any], key: str, value: Any) -> Iterator[None]:
    """Temporarily override a dictionary value within a context manager."""

    original = mapping.get(key, None)
    mapping[key] = value
    try:
        yield
    finally:
        if original is None and key not in mapping:
            return
        if original is None:
            mapping.pop(key, None)
        else:
            mapping[key] = original
