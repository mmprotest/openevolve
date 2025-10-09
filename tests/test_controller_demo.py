from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any, Sequence

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
