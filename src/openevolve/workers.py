"""Evaluation workers (simplified placeholder)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Mapping


class WorkerPool:
    """Thread based worker pool for evaluation jobs."""

    def __init__(self, max_workers: int) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, fn: Callable[..., Mapping[str, float]], *args, **kwargs):  # type: ignore[override]
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
