"""Behavioural tests for the evolution controller."""

from __future__ import annotations

import asyncio
from textwrap import dedent

import pytest

from openevolve.blocks import extract_blocks
from openevolve.controller import EvolutionController, EvolutionTask
from openevolve.llm_client import GenerationResult, LLMClientProtocol


class _FakeClient(LLMClientProtocol):
    """Return predefined candidates for controller tests."""

    def __init__(self, batches: list[list[str]]) -> None:
        self._batches = batches
        self.calls: int = 0

    async def generate(self, *, prompt: str, system: str, model=None, n=1, temperature=0.7, extra_messages=None):
        del prompt, system, model, n, temperature, extra_messages
        if self.calls >= len(self._batches):
            raise AssertionError("No more batches configured for fake client")
        batch = self._batches[self.calls]
        self.calls += 1
        return GenerationResult(candidates=batch)

    async def aclose(self) -> None:  # pragma: no cover - not used in tests
        return None


def test_stop_on_first_requires_improvement(tmp_path) -> None:
    source = dedent(
        """
        def evolve_sort(values):
            # EVOLVE-BLOCK-START demo
            arr = list(values)
            n = len(arr)
            for i in range(n):
                for j in range(0, n - i - 1):
                    if arr[j] > arr[j + 1]:
                        arr[j], arr[j + 1] = arr[j + 1], arr[j]
            return arr
            # EVOLVE-BLOCK-END
        """
    ).lstrip()

    program_path = tmp_path / "program.py"
    program_path.write_text(source)

    def _evaluate(updated_source: str) -> dict[str, float]:
        namespace: dict[str, object] = {}
        exec(updated_source, namespace)  # noqa: S102 - evaluation sandboxed by test harness
        evolve_sort = namespace["evolve_sort"]
        result = evolve_sort([3, 1, 2])
        accuracy = 1.0 if result == [1, 2, 3] else 0.0
        code_length = float(len(updated_source.strip().splitlines()))
        return {"accuracy": accuracy, "time_ms": 0.0, "code_length": code_length}

    def _score(metrics: dict[str, float]) -> float:
        return metrics["accuracy"] * 1_000 - metrics["code_length"]

    bad_diff = dedent(
        """
        <<<<<<< SEARCH
        arr = list(values)
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
        return arr
        =======
        return values
        >>>>>>> REPLACE
        """
    ).strip()

    good_diff = dedent(
        """
        <<<<<<< SEARCH
        arr = list(values)
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
        return arr
        =======
        return sorted(values)
        >>>>>>> REPLACE
        """
    ).strip()

    client = _FakeClient([[bad_diff, good_diff]])

    task = EvolutionTask(
        name="demo",
        description="",
        program_path=program_path,
        evaluation=_evaluate,
        scoring=_score,
    )

    controller = EvolutionController(
        client=client,
        candidates=2,
        max_rounds=1,
        stop_on_first=True,
    )

    metrics = asyncio.run(controller.evolve_once(task))

    assert metrics["accuracy"] == pytest.approx(1.0)
    blocks = extract_blocks(program_path.read_text())
    assert "return sorted(values)" in blocks[0].content
    assert client.calls == 1
