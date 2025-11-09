"""Tests for the algorithmic optimisation evaluation harness."""
from __future__ import annotations

import logging
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tasks.algorithmic_optimization.evaluate import evaluate


def test_evaluate_rejects_inplace_sort_returning_none() -> None:
    """Implementations must return the sorted sequence rather than ``None``."""

    source = textwrap.dedent(
        """
        from typing import Iterable


        def evolve_sort(values: Iterable[int]):
            values.sort()
            # Implicit ``None`` return mirrors ``list.sort`` semantics.
        """
    )

    metrics = evaluate(source)

    assert metrics["accuracy"] == 0.0


def test_evaluate_accepts_inplace_sort_returning_sequence() -> None:
    """In-place algorithms that return the mutated list should still pass."""

    source = textwrap.dedent(
        """
        from typing import Iterable


        def evolve_sort(values: Iterable[int]):
            values.sort()
            return values
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


def test_evaluate_logs_contract_violation(caplog) -> None:
    """Returning ``None`` surfaces a debug log to aid troubleshooting."""

    source = textwrap.dedent(
        """
        from typing import Iterable


        def evolve_sort(values: Iterable[int]):
            values.sort()
            return None
        """
    )

    with caplog.at_level(logging.DEBUG, logger="tasks.algorithmic_optimization.evaluate"):
        metrics = evaluate(source)

    assert metrics["accuracy"] == 0.0
    assert "contract violation" in caplog.text
