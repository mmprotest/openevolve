"""Evaluation routine for the algorithmic optimisation example."""

from __future__ import annotations

import random
import time
from statistics import mean
from typing import Mapping

from openevolve.sandbox import run_in_sandbox

_RNG = random.Random(1337)

DATASETS: tuple[tuple[int, ...], ...] = (
    (5, 1, 3, 9, 0),
    tuple(range(32, 0, -1)),
    tuple(_RNG.randint(0, 100) for _ in range(25)),
    (1, 2, 2, 2, 3, 3, 1, 0),
)


def evaluate(source: str) -> Mapping[str, float]:
    """Return metrics capturing correctness, speed, and brevity."""

    module_globals = run_in_sandbox(source)
    evolve_sort = module_globals["evolve_sort"]

    durations: list[float] = []
    successes = 0
    for dataset in DATASETS:
        payload = list(dataset)
        start = time.perf_counter()
        result = evolve_sort(payload)
        durations.append((time.perf_counter() - start) * 1000)
        if list(result) == sorted(dataset):
            successes += 1

    accuracy = successes / len(DATASETS)
    average_ms = mean(durations) if durations else 0.0
    code_length = float(len(source.strip().splitlines()))

    return {
        "accuracy": accuracy,
        "time_ms": average_ms,
        "code_length": code_length,
    }
