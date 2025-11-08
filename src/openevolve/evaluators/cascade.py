"""Asynchronous evaluator cascade execution."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .base import BaseEvaluator, EvaluationResult


async def run_cascade(
    workdir: str | Path,
    candidate: dict,
    evaluators: list[BaseEvaluator],
    max_parallel: int,
    cancel_on_fail: bool,
) -> dict[str, EvaluationResult]:
    """Execute evaluators with parallelism and timeouts."""

    if not evaluators:
        return {}

    workdir_path = Path(workdir)
    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(max_parallel)
    executor = ThreadPoolExecutor(max_workers=max_parallel)
    results: dict[str, EvaluationResult] = {}
    tasks: list[asyncio.Task] = []

    evaluators_sorted = sorted(evaluators, key=lambda ev: getattr(ev, "timeout_s", 30))

    async def _run_eval(evaluator: BaseEvaluator) -> tuple[str, EvaluationResult]:
        async with semaphore:
            def _call() -> tuple[str, EvaluationResult]:
                try:
                    result = evaluator.evaluate(workdir_path, candidate)
                except Exception as exc:  # pragma: no cover - defensive
                    result = EvaluationResult(value=0.0, passed=False, cost_ms=0, error=str(exc))
                return evaluator.name, result

            timeout = getattr(evaluator, "timeout_s", 30)
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(executor, _call),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                return evaluator.name, EvaluationResult(
                    value=0.0,
                    passed=False,
                    cost_ms=timeout * 1000,
                    error="timeout",
                )

    try:
        for evaluator in evaluators_sorted:
            tasks.append(asyncio.create_task(_run_eval(evaluator)))

        for task in asyncio.as_completed(tasks):
            name, result = await task
            results[name] = result
            if cancel_on_fail and not result.get("passed", False):
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                break
    finally:
        executor.shutdown(wait=False)

    return results
