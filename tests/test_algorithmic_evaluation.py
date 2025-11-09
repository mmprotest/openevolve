"""Tests for the algorithmic optimisation evaluation harness."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tasks.algorithmic_optimization.evaluate import evaluate


def test_evaluate_accepts_inplace_sort_returning_none() -> None:
    """Implementations that sort in-place but return ``None`` should pass."""

    source = textwrap.dedent(
        """
        from typing import Iterable


        def evolve_sort(values: Iterable[int]):
            values.sort()
            # Implicit ``None`` return mirrors ``list.sort`` semantics.
        """
    )

    metrics = evaluate(source)

    assert metrics["accuracy"] == 1.0


def test_evaluate_accepts_generator_result() -> None:
    """Generator returns should be realised and validated correctly."""

    source = textwrap.dedent(
        """
        from typing import Iterable


        def evolve_sort(values: Iterable[int]):
            return (value for value in sorted(values))
        """
    )

    metrics = evaluate(source)

    assert metrics["accuracy"] == 1.0
