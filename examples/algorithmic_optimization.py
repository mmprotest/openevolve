"""Run the algorithmic optimisation demo task end-to-end using a live LLM."""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for entry in (ROOT, SRC):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from openevolve.controller import EvolutionController, EvolutionTask
from tasks.algorithmic_optimization.evaluate import evaluate

TASK_DESCRIPTION = (
    "Improve the EVOLVE block to keep accuracy at 1.0 while reducing latency and code size."
)

PROGRAM_PATH = (
    ROOT
    / "tasks"
    / "algorithmic_optimization"
    / "program.py"
)


def _print_metrics(title: str, metrics: dict[str, float]) -> None:
    print(title)
    for name, value in metrics.items():
        print(f"  {name:>12}: {value:.4f}")


def main() -> None:
    baseline_source = PROGRAM_PATH.read_text(encoding="utf-8")
    baseline_metrics = evaluate(baseline_source)
    _print_metrics("Baseline bubble sort metrics:", dict(baseline_metrics))

    with tempfile.TemporaryDirectory() as tmpdir:
        candidate_program = Path(tmpdir) / "program.py"
        candidate_program.write_text(baseline_source, encoding="utf-8")

        task = EvolutionTask(
            name="algorithmic-optimisation-demo",
            description=TASK_DESCRIPTION,
            program_path=candidate_program,
            evaluation=evaluate,
        )
        controller = EvolutionController()
        improved_metrics = asyncio.run(controller.evolve_once(task))

        _print_metrics("\nImproved candidate metrics:", dict(improved_metrics))

        updated_source = candidate_program.read_text(encoding="utf-8")
        print("\nUpdated EVOLVE block:\n")
        print(updated_source)


if __name__ == "__main__":
    main()
