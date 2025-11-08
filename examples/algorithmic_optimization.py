"""Run the algorithmic optimisation demo task end-to-end using a live LLM."""

from __future__ import annotations

import asyncio
import argparse
import logging
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for entry in (ROOT, SRC):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from typing import Mapping

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        help="Override the model used for diff generation. Defaults to the configured primary model.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Sampling temperature passed to the language model (default: 0.7).",
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=3,
        help="Number of diff candidates to request per round (default: 3).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Maximum number of language-model rounds to attempt before giving up (default: 3).",
    )
    parser.add_argument(
        "--evolutions",
        type=int,
        default=1,
        help=(
            "Number of sequential evolution cycles to run. Each cycle starts from the best "
            "candidate produced by the previous one (default: 1)."
        ),
    )
    parser.add_argument(
        "--full-search",
        action="store_true",
        help=(
            "Evaluate every requested round and candidate instead of stopping at the first viable mutation. "
            "Returns the best-scoring program after the search completes."
        ),
    )
    parser.add_argument(
        "--system-prompt",
        help="Optional system prompt override sent to the model when mutating the EVOLVE block.",
    )
    parser.add_argument(
        "--description",
        default=TASK_DESCRIPTION,
        help="Custom task description passed to the model.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging level for the evolution controller (default: INFO).",
    )
    return parser.parse_args()


def _print_metrics(title: str, metrics: dict[str, float]) -> None:
    print(title)
    for name, value in metrics.items():
        print(f"  {name:>12}: {value:.4f}")


def _score_metrics(metrics: Mapping[str, float]) -> float:
    """Combine metrics to reward accuracy and penalise latency/length."""

    accuracy = metrics.get("accuracy", 0.0)
    time_ms = metrics.get("time_ms", 0.0)
    code_length = metrics.get("code_length", 0.0)
    # Weight accuracy heavily to ensure correctness dominates the objective.
    return accuracy * 1_000 - time_ms - code_length


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    baseline_source = PROGRAM_PATH.read_text(encoding="utf-8")
    baseline_metrics = evaluate(baseline_source)
    _print_metrics("Baseline bubble sort metrics:", dict(baseline_metrics))

    with tempfile.TemporaryDirectory() as tmpdir:
        candidate_program = Path(tmpdir) / "program.py"

        task = EvolutionTask(
            name="algorithmic-optimisation-demo",
            description=args.description,
            program_path=candidate_program,
            evaluation=evaluate,
            scoring=_score_metrics,
        )
        controller = EvolutionController(
            model=args.model,
            temperature=args.temperature,
            candidates=args.candidates,
            max_rounds=args.rounds,
            system_prompt=args.system_prompt or EvolutionController.DEFAULT_SYSTEM_PROMPT,
            stop_on_first=not args.full_search,
            logger=logging.getLogger("openevolve.controller"),
        )

        current_source = baseline_source
        for cycle in range(1, args.evolutions + 1):
            candidate_program.write_text(current_source, encoding="utf-8")
            print(f"\n=== Evolution cycle {cycle} ===")

            improved_metrics = asyncio.run(
                controller.evolve_once(
                    task,
                    stop_on_first=not args.full_search,
                )
            )

            _print_metrics(
                f"\nImproved candidate metrics (cycle {cycle}):",
                dict(improved_metrics),
            )

            updated_source = candidate_program.read_text(encoding="utf-8")
            if updated_source == current_source:
                print(
                    "\nNo viable candidate was found; leaving the current implementation unchanged."
                )
                break

            print("\nUpdated EVOLVE block:\n")
            print(updated_source)

            current_source = updated_source

        if current_source != baseline_source:
            print("\nFinal evolved implementation:\n")
            print(current_source)
        else:
            print("\nEvolution finished without improving the baseline implementation.")


if __name__ == "__main__":
    main()
