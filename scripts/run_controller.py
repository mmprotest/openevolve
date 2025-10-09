"""Entry point for running the evolutionary controller."""

from __future__ import annotations

import argparse
from pathlib import Path

from openevolve.controller import EvolutionController, EvolutionTask
from openevolve.database import Database
from tasks.speed_sort import evaluate as speed_sort_eval
from tasks.toy_sum_squares import evaluate as toy_eval

TASKS = {
    "speed_sort": (
        "Design a fast sorting algorithm with minimal overhead.",
        Path("tasks/speed_sort/program.py"),
        speed_sort_eval.evaluate,
    ),
    "toy_sum_squares": (
        "Minimise error when computing the sum of squares for integer lists.",
        Path("tasks/toy_sum_squares/program.py"),
        toy_eval.evaluate,
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the OpenEvolve controller")
    parser.add_argument("--task", choices=TASKS.keys(), required=True)
    args = parser.parse_args()

    description, program_path, evaluator = TASKS[args.task]
    controller = EvolutionController()
    task = EvolutionTask(
        name=args.task,
        description=description,
        program_path=program_path,
        evaluation=evaluator,
    )

    import asyncio

    asyncio.run(controller.evolve_once(task))


if __name__ == "__main__":
    main()
