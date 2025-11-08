"""Evaluator base classes and reference implementations."""

from __future__ import annotations

import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypedDict


class EvaluationResult(TypedDict, total=False):
    value: float
    passed: bool
    cost_ms: int
    error: str | None


class BaseEvaluator(ABC):
    name: str
    weight: float = 1.0
    timeout_s: int = 30

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abstractmethod
    def evaluate(self, workdir: Path, candidate: dict) -> EvaluationResult:
        """Execute evaluation for candidate within workdir."""


class UnitTestsEvaluator(BaseEvaluator):
    """Run pytest within the candidate workspace."""

    name = "tests"
    pytest_args: list[str] = ["pytest", "-q"]

    def evaluate(self, workdir: Path, candidate: dict) -> EvaluationResult:
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                self.pytest_args,
                cwd=workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except FileNotFoundError as exc:  # pragma: no cover - environment issue
            return EvaluationResult(value=0.0, passed=False, cost_ms=0, error=str(exc))
        duration = int((time.perf_counter() - start) * 1000)
        passed = proc.returncode == 0
        return EvaluationResult(
            value=1.0 if passed else 0.0,
            passed=passed,
            cost_ms=duration,
            error=None if passed else proc.stdout,
        )


class LintsEvaluator(BaseEvaluator):
    """Simple static checks based on patch size or formatting markers."""

    name = "lints"
    max_lines: int = 400

    def evaluate(self, workdir: Path, candidate: dict) -> EvaluationResult:  # noqa: ARG002
        patch = candidate.get("patch", "")
        added_lines = sum(1 for line in patch.splitlines() if line.startswith("+"))
        passed = added_lines <= self.max_lines
        value = float(self.max_lines - added_lines)
        return EvaluationResult(
            value=value,
            passed=passed,
            cost_ms=1,
            error=None if passed else f"Too many added lines: {added_lines} > {self.max_lines}",
        )


class PerfEvaluator(BaseEvaluator):
    """Measure performance of a provided callable or script."""

    name = "perf"
    target_key: str = "perf_target"
    budget_ms: int = 100

    def evaluate(self, workdir: Path, candidate: dict) -> EvaluationResult:  # noqa: ARG002
        target = candidate.get(self.target_key)
        if target is None:
            return EvaluationResult(value=0.0, passed=True, cost_ms=0, error=None)
        if callable(target):
            start = time.perf_counter()
            target()
            duration = int((time.perf_counter() - start) * 1000)
        else:
            script_path = Path(target)
            start = time.perf_counter()
            subprocess.run(["python", str(script_path)], cwd=workdir, check=False)
            duration = int((time.perf_counter() - start) * 1000)
        passed = duration <= self.budget_ms
        return EvaluationResult(
            value=float(duration),
            passed=passed,
            cost_ms=duration,
            error=None if passed else f"duration {duration}ms exceeds budget {self.budget_ms}ms",
        )
