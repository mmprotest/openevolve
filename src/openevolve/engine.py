"""Evolution orchestration engine."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Callable

from .apply import apply_patch, load_blocks, write_if_changed
from .db import ProgramDB
from .evaluators import BaseEvaluator, LintsEvaluator, PerfEvaluator, UnitTestsEvaluator, run_cascade
from .meta_prompt import evolve_meta_prompts, seed_meta_prompts, select_meta_prompts
from .prompt_sampler import build_prompt
from .selection import Archive

logger = logging.getLogger(__name__)


EVALUATOR_REGISTRY = {
    "UnitTestsEvaluator": UnitTestsEvaluator,
    "LintsEvaluator": LintsEvaluator,
    "PerfEvaluator": PerfEvaluator,
}


def _metrics_bool(cfg_metrics: dict[str, str | bool]) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for name, mode in cfg_metrics.items():
        if isinstance(mode, str):
            result[name] = mode.lower() != "minimize"
        else:
            result[name] = bool(mode)
    return result


def _ensure_generations(db: ProgramDB, run_id: str) -> int:
    cands = db.get_candidates_by_run(run_id)
    if not cands:
        return 0
    return max(int(cand.get("gen", 0)) for cand in cands) + 1


def _load_evaluators(config: dict) -> list[BaseEvaluator]:
    evaluators: list[BaseEvaluator] = []
    for entry in config.get("evaluators", []):
        name = entry.get("name")
        params = {k: v for k, v in entry.items() if k != "name"}
        factory = EVALUATOR_REGISTRY.get(name)
        if not factory:
            raise ValueError(f"Unknown evaluator {name}")
        evaluators.append(factory(**params))
    return evaluators


async def evolve(run_id: str, cfg: dict, llm_call: Callable[[str], str]) -> None:
    """Run the evolutionary search loop."""

    db = ProgramDB(cfg["db_path"])
    db.upsert_run(run_id, cfg)
    seed_meta_prompts(db)

    rng = random.Random(cfg.get("seed"))
    workdir = Path(cfg.get("workdir", ".")).resolve()
    target = cfg.get("task", {}).get("target_file")
    if not target:
        raise ValueError("task.target_file must be specified")
    target_path = (workdir / target).resolve()
    task_desc = cfg.get("task", {}).get("description", "")
    scope = cfg.get("evolution", {}).get("scope", "blocks")
    sampler_cfg = cfg.get("sampler", {})
    cascade_cfg = cfg.get("cascade", {})
    archive_cfg = cfg.get("archive", {})
    selection_cfg = cfg.get("selection", {})
    population_size = int(cfg.get("population_size", 8))
    generations = int(cfg.get("generations", 1))
    dry_run = bool(cfg.get("dry_run", False))

    metrics_cfg = cfg.get("metrics", {})
    metrics_bool = _metrics_bool(metrics_cfg)
    archive = Archive(
        capacity=int(archive_cfg.get("capacity", 200)),
        metrics=metrics_bool,
        k_novelty=int(archive_cfg.get("k_novelty", 10)),
    )

    run_dir = Path(cfg.get("artifacts_root", "runs")) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "logs.jsonl"

    if not log_path.exists():
        log_path.touch()

    def log_event(payload: dict) -> None:
        payload["timestamp"] = time.time()
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload) + "\n")

    configured_blocks = cfg.get("task", {}).get("evolve_blocks")
    if configured_blocks:
        block_ranges = configured_blocks
    else:
        block_ranges = [(block.start_line, block.end_line) for block in load_blocks(target_path)]

    start_gen = _ensure_generations(db, run_id)
    evaluators = _load_evaluators(cascade_cfg)

    for gen in range(start_gen, generations):
        gen_dir = run_dir / f"gen_{gen:03d}"
        gen_dir.mkdir(parents=True, exist_ok=True)
        meta_prompts = select_meta_prompts(db, max(1, cfg.get("meta_prompt", {}).get("selection_top_k", 3)))
        rng.shuffle(meta_prompts)
        contributions: dict[str, list[str]] = {}

        parents = archive.sample_mixture(
            int(selection_cfg.get("elite", 0)),
            int(selection_cfg.get("novel", 0)),
            int(selection_cfg.get("young", 0)),
        )

        for member in range(population_size):
            meta = meta_prompts[member % len(meta_prompts)]
            prompt = build_prompt(
                run_id=run_id,
                db=db,
                budget_tokens=int(sampler_cfg.get("budget_tokens", 4000)),
                task_desc=task_desc,
                target_file=target,
                evolve_blocks=block_ranges,
                metrics=list(metrics_cfg.keys()),
                sampler_cfg=sampler_cfg,
                meta_prompt_template=meta["template"],
            )
            prompt_path = gen_dir / f"candidate_{member:02d}_prompt.txt"
            prompt_path.write_text(prompt, encoding="utf-8")

            if dry_run:
                continue

            patch_text = await asyncio.to_thread(llm_call, prompt)
            cand_id = str(uuid.uuid4())
            before_source = target_path.read_text(encoding="utf-8")
            outcome = apply_patch(target_path, patch_text, scope=scope)
            candidate_record = {
                "cand_id": cand_id,
                "parent_ids": parents,
                "meta_prompt_id": meta["meta_prompt_id"],
                "filepath": target,
                "patch": patch_text,
                "code_snapshot": before_source,
                "gen": gen,
                "novelty": 0.0,
                "age": 0,
            }
            if not outcome.success or outcome.new_source is None:
                candidate_record["error"] = outcome.error or "apply failed"
                db.insert_candidate(run_id, candidate_record)
                continue

            write_if_changed(target_path, outcome.new_source)
            candidate_record["code_snapshot"] = outcome.new_source
            db.insert_candidate(run_id, candidate_record)
            contributions.setdefault(meta["meta_prompt_id"], []).append(cand_id)

            if evaluators:
                cascade_results = await run_cascade(
                    workdir=workdir,
                    candidate=candidate_record,
                    evaluators=evaluators,
                    max_parallel=int(cascade_cfg.get("max_parallel", 4)),
                    cancel_on_fail=bool(cascade_cfg.get("cancel_on_fail", False)),
                )
                metrics = {name: res.get("value", 0.0) for name, res in cascade_results.items()}
                passed = {name: res.get("passed", False) for name, res in cascade_results.items()}
                cost_ms = {name: res.get("cost_ms", 0) for name, res in cascade_results.items()}
                errors = {name: res.get("error") for name, res in cascade_results.items()}
                db.insert_evaluations(cand_id, metrics, passed, cost_ms, errors)

                if scope == "wholefile" and cfg.get("evolution", {}).get("apply_safe_revert", False):
                    if any(not ok for ok in passed.values()):
                        write_if_changed(target_path, before_source)
            write_if_changed(target_path, before_source)

        all_cands = db.get_candidates_by_run(run_id)
        evals = db.get_candidate_evals([cand["cand_id"] for cand in all_cands])
        archive.update(all_cands, evals, current_gen=gen)

        for cand_id, entry in archive.entries.items():
            stored = db.get_candidate(cand_id)
            if not stored:
                continue
            stored["novelty"] = entry.novelty
            stored["age"] = entry.age
            db.insert_candidate(run_id, stored)

        evolve_meta_prompts(db, contributions)

        log_event(
            {
                "generation": gen,
                "candidates": list(contributions.values()),
                "parents": parents,
                "archive_size": len(archive.entries),
            }
        )

    if dry_run:
        logger.info("Dry run completed for run %s", run_id)
