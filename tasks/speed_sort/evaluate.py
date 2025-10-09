"""Evaluation for speed_sort task."""

from __future__ import annotations

import random
from typing import Mapping

from openevolve.sandbox import run_in_sandbox

TASK_DESCRIPTION = "Design a fast sorting algorithm with minimal overhead."


def evaluate(source: str) -> Mapping[str, float]:
    module_globals = run_in_sandbox(source)
    func = module_globals["core_algorithm"]
    datasets = [
        [5, 3, 9, 1],
        [random.randint(0, 100) for _ in range(10)],
        list(range(10, 0, -1)),
    ]
    correctness = 0
    for data in datasets:
        if func(list(data)) == sorted(data):
            correctness += 1
    return {"correct": correctness / len(datasets)}
