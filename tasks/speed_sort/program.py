"""Baseline implementation for speed_sort task."""

from __future__ import annotations


def core_algorithm(values: list[int]) -> list[int]:
    """Stable, efficient sort candidate."""

    # EVOLVE-BLOCK-START core_algorithm
    return sorted(values)
    # EVOLVE-BLOCK-END
