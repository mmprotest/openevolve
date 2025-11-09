"""Evaluation routine for the algorithmic optimisation example."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterable
from statistics import mean
from typing import Mapping

from openevolve.sandbox import run_in_sandbox

LOGGER = logging.getLogger(__name__)

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
    LOGGER.debug("Evaluating candidate across %s dataset(s)", len(DATASETS))
    for index, dataset in enumerate(DATASETS):
        payload = list(dataset)
        LOGGER.debug(
            "Dataset %s: evaluating %s values", index + 1, len(payload)
        )
        start = time.perf_counter()
        result = evolve_sort(payload)
        duration_ms = (time.perf_counter() - start) * 1000
        durations.append(duration_ms)
        LOGGER.debug(
            "Dataset %s: evolve_sort returned %r (type=%s) in %.4f ms",
            index + 1,
            result,
            type(result).__name__,
            duration_ms,
        )

        if isinstance(result, Iterable):
            try:
                candidate_output = list(result)
                LOGGER.debug(
                    "Dataset %s: materialised candidate output (first 5)=%s",
                    index + 1,
                    candidate_output[:5],
                )
            except TypeError:
                # Guard against objects claiming to be iterable but raising at iteration time.
                LOGGER.debug(
                    "Dataset %s: result raised TypeError during iteration", index + 1
                )
                candidate_output = []
        else:
            # Non-iterable return values cannot represent a sorted sequence.
            LOGGER.debug(
                "Dataset %s: result was not iterable (type=%s)",
                index + 1,
                type(result).__name__,
            )
            candidate_output = []

        if result is None:
            # ``evolve_sort`` is expected to return the sorted sequence; returning ``None``
            # indicates the contract was violated even if the input list was mutated.
            LOGGER.debug(
                "Dataset %s: result was None; treating as contract violation", index + 1
            )
            candidate_output = []

        if candidate_output == sorted(dataset):
            successes += 1
            LOGGER.debug("Dataset %s: produced a correctly sorted sequence", index + 1)
        else:
            preview = candidate_output[:10]
            LOGGER.debug(
                "Dataset %s: produced incorrect ordering (first %s of %s)=%s",
                index + 1,
                len(preview),
                len(candidate_output),
                preview,
            )

    accuracy = successes / len(DATASETS)
    average_ms = mean(durations) if durations else 0.0
    code_length = float(len(source.strip().splitlines()))

    LOGGER.debug(
        "Evaluation finished: accuracy=%.4f time_ms=%.4f code_length=%.1f",
        accuracy,
        average_ms,
        code_length,
    )

    return {
        "accuracy": accuracy,
        "time_ms": average_ms,
        "code_length": code_length,
    }
