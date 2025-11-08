"""Baseline sorting heuristic targeted by the algorithmic optimisation example."""

from __future__ import annotations

from typing import Iterable


def evolve_sort(values: Iterable[int]) -> list[int]:
    """Return a sorted list. Baseline is intentionally inefficient."""

    # EVOLVE-BLOCK-START algorithmic_sort
    arr = list(values)
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
    # EVOLVE-BLOCK-END


def is_sorted(values: Iterable[int]) -> bool:
    """Utility used by evaluators and quick manual checks."""

    iterator = iter(values)
    try:
        previous = next(iterator)
    except StopIteration:
        return True
    for current in iterator:
        if current < previous:
            return False
        previous = current
    return True
