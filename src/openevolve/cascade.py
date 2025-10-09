"""Cascade orchestration helpers."""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Sequence

from .evaluation import EvaluationOutcome, run_cascade


class CascadeBuilder:
    """Collect staged evaluators and execute them in order."""

    def __init__(self) -> None:
        self._stages: list[tuple[str, Callable[[str], Mapping[str, float]]]] = []

    def stage(self, name: str, evaluator: Callable[[str], Mapping[str, float]]) -> None:
        self._stages.append((name, evaluator))

    def build(self) -> Sequence[tuple[str, Callable[[str], Mapping[str, float]]]]:
        return tuple(self._stages)

    def run(self, candidate_source: str) -> list[EvaluationOutcome]:
        return run_cascade(self._stages, candidate_source)
