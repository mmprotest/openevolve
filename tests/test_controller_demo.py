from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openevolve.controller import EvolutionController, EvolutionTask
from openevolve.llm_client import GenerationResult, LLMClientProtocol
from tasks.toy_sum_squares import evaluate as toy_eval

DEMO_DIFF = """<<<<<<< SEARCH
    total = 0
    for value in values:
        total += value * value
    return total
=======
    return sum(value * value for value in values)
>>>>>>> REPLACE
""".strip()


class _StaticClient(LLMClientProtocol):
    def __init__(self, diff: str) -> None:
        self._diff = diff

    async def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        return GenerationResult(candidates=[self._diff])

    async def aclose(self) -> None:  # pragma: no cover - nothing allocated
        return None


def test_controller_accepts_static_diff(tmp_path: Path) -> None:
    program_source = Path("tasks/toy_sum_squares/program.py").read_text()
    program_path = tmp_path / "program.py"
    program_path.write_text(program_source)

    task = EvolutionTask(
        name="toy-demo",
        description=toy_eval.TASK_DESCRIPTION,
        program_path=program_path,
        evaluation=toy_eval.evaluate,
    )
    controller = EvolutionController(client=_StaticClient(DEMO_DIFF))

    metrics = asyncio.run(controller.evolve_once(task))

    assert metrics["correct"] == 1.0
    updated_source = program_path.read_text()
    assert "sum(value * value for value in values)" in updated_source


class _InvalidClient(LLMClientProtocol):
    async def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        return GenerationResult(candidates=["invalid diff"])

    async def aclose(self) -> None:  # pragma: no cover - no resources
        return None


def test_controller_returns_baseline_when_no_candidate(tmp_path: Path) -> None:
    program_source = Path("tasks/toy_sum_squares/program.py").read_text()
    program_path = tmp_path / "program.py"
    program_path.write_text(program_source)

    task = EvolutionTask(
        name="toy-demo",
        description=toy_eval.TASK_DESCRIPTION,
        program_path=program_path,
        evaluation=toy_eval.evaluate,
    )
    controller = EvolutionController(client=_InvalidClient())

    baseline_metrics = dict(toy_eval.evaluate(program_source))
    metrics = asyncio.run(controller.evolve_once(task))

    assert metrics == baseline_metrics
    assert program_path.read_text() == program_source


class _RoundRobinClient(LLMClientProtocol):
    def __init__(self, batches: Sequence[Sequence[str]]) -> None:
        self._batches = list(batches)
        self._index = 0

    async def generate(
        self,
        *,
        prompt: str,
        system: str,
        model: str | None = None,
        n: int = 1,
        temperature: float = 0.7,
        extra_messages: Sequence[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        if self._index < len(self._batches):
            candidates = list(self._batches[self._index])
        else:
            candidates = list(self._batches[-1])
        self._index += 1
        return GenerationResult(candidates=candidates)

    async def aclose(self) -> None:  # pragma: no cover - no resources
        return None


_RETURN_TWO = """<<<<<<< SEARCH
    return 1
=======
    return 2
>>>>>>> REPLACE
""".strip()


_RETURN_TEN = """<<<<<<< SEARCH
    return 2
=======
    return 10
>>>>>>> REPLACE
""".strip()


def _score(metrics: Mapping[str, float]) -> float:
    return metrics.get("fitness", 0.0)


def _evaluate(source: str) -> Mapping[str, float]:
    namespace: dict[str, Any] = {}
    exec(source, namespace)  # noqa: S102 - test harness
    value = namespace["evolve"]()
    return {"fitness": float(value)}


def test_controller_full_search_keeps_best_candidate(tmp_path: Path) -> None:
    program_source = """
def evolve() -> int:
    # EVOLVE-BLOCK-START evolve
    return 1
    # EVOLVE-BLOCK-END
""".strip()
    program_path = tmp_path / "program.py"
    program_path.write_text(program_source)

    task = EvolutionTask(
        name="toy-full-search",
        description="Improve return value",
        program_path=program_path,
        evaluation=_evaluate,
        scoring=_score,
    )
    controller = EvolutionController(
        client=_RoundRobinClient([[_RETURN_TWO], [_RETURN_TEN]]),
        candidates=1,
        max_rounds=2,
        stop_on_first=False,
    )

    metrics = asyncio.run(controller.evolve_once(task, stop_on_first=False))

    assert metrics["fitness"] == 10.0
    assert "return 10" in program_path.read_text()
