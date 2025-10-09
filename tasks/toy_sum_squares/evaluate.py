"""Evaluation logic for toy task."""

from __future__ import annotations

from importlib import util
from types import ModuleType
from typing import Mapping

from openevolve.sandbox import run_in_sandbox


TASK_DESCRIPTION = "Minimise error when computing the sum of squares for integer lists."


def evaluate(source: str) -> Mapping[str, float]:
    module_globals = run_in_sandbox(source)
    func = module_globals["sum_of_squares"]
    inputs = [[1, 2, 3], [0, -1, 5], [10]]
    expected = [14, 26, 100]
    correct = 0
    for values, target in zip(inputs, expected):
        if func(values) == target:
            correct += 1
    return {"correct": correct / len(inputs)}
