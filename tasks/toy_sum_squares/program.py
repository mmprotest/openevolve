"""Toy task for evolving sum of squares."""

from __future__ import annotations


def sum_of_squares(values: list[int]) -> int:
    """Compute the sum of squared elements."""

    # EVOLVE-BLOCK-START sum_of_squares
    total = 0
    for value in values:
        total += value * value
    return total
    # EVOLVE-BLOCK-END
