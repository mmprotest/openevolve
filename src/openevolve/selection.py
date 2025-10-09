"""Selection utilities for evolutionary search."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable, Sequence


def dominates(a: dict[str, float], b: dict[str, float], objectives: Sequence[str]) -> bool:
    """Return True if metric dict *a* dominates *b* for objectives (higher is better)."""

    better_or_equal = True
    strictly_better = False
    for objective in objectives:
        a_val = a.get(objective)
        b_val = b.get(objective)
        if a_val is None or b_val is None:
            raise KeyError(f"Missing objective '{objective}' in candidate metrics")
        if a_val < b_val:
            better_or_equal = False
            break
        if a_val > b_val:
            strictly_better = True
    return better_or_equal and strictly_better


def pareto_front(candidates: Sequence[dict[str, float]], objectives: Sequence[str]) -> list[int]:
    """Return indices of Pareto optimal candidates."""

    front: list[int] = []
    for idx, metrics in enumerate(candidates):
        dominated = False
        for jdx, other in enumerate(candidates):
            if jdx == idx:
                continue
            if dominates(other, metrics, objectives):
                dominated = True
                break
        if not dominated:
            front.append(idx)
    return front


def euclidean_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    return sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


def novelty_score(
    descriptor: Sequence[float],
    archive: Sequence[Sequence[float]],
    *,
    k: int = 5,
) -> float:
    """Compute novelty as mean distance to k nearest neighbours in archive."""

    if not archive:
        return float("inf")

    distances = sorted(euclidean_distance(descriptor, other) for other in archive)
    sample = distances[: max(1, min(k, len(distances)))]
    return sum(sample) / len(sample)


def update_archive(
    archive: list[Sequence[float]],
    descriptor: Sequence[float],
    *,
    max_size: int,
) -> None:
    """Append descriptor to archive with bounded size (FIFO)."""

    archive.append(tuple(descriptor))
    if len(archive) > max_size:
        del archive[0 : len(archive) - max_size]
