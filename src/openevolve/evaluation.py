"""Evaluation utilities for tasks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


@dataclass(slots=True)
class EvaluationOutcome:
    stage: str
    metrics: Mapping[str, float]


StageCallable = Callable[[str], Mapping[str, float]]


def run_cascade(stages: Sequence[tuple[str, StageCallable]], candidate_source: str) -> list[EvaluationOutcome]:
    """Run synchronous cascade returning metrics per stage."""

    outcomes: list[EvaluationOutcome] = []
    for name, stage_callable in stages:
        metrics = stage_callable(candidate_source)
        outcomes.append(EvaluationOutcome(stage=name, metrics=metrics))
    return outcomes
