"""Run a deterministic offline demo of the evolution loop."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (SRC_ROOT, REPO_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

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


class StaticDiffClient(LLMClientProtocol):
    """Client that always returns the same diff for demonstration purposes."""

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
        return GenerationResult(candidates=[self._diff], raw_response={"provider": "static-demo"})

    async def aclose(self) -> None:  # pragma: no cover - nothing to clean up
        return None


def prepare_program_copy() -> Path:
    source_path = REPO_ROOT / "tasks" / "toy_sum_squares" / "program.py"
    runs_dir = REPO_ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    demo_program_path = runs_dir / "toy_sum_squares_demo.py"
    demo_program_path.write_text(source_path.read_text())
    return demo_program_path


def main() -> None:
    program_path = prepare_program_copy()
    controller = EvolutionController(client=StaticDiffClient(DEMO_DIFF))
    task = EvolutionTask(
        name="toy_sum_squares_demo",
        description=toy_eval.TASK_DESCRIPTION,
        program_path=program_path,
        evaluation=toy_eval.evaluate,
    )
    metrics = asyncio.run(controller.evolve_once(task))
    print("Accepted metrics:", metrics)
    print("Updated program saved to:", program_path)
    print("\n--- Updated Program ---\n")
    print(program_path.read_text())


if __name__ == "__main__":
    main()
