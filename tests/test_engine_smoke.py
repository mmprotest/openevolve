from __future__ import annotations

import asyncio
import json
from pathlib import Path

from openevolve.engine import evolve

PATCH = json.dumps(
    [
        {
            "block_id": "sum_of_squares",
            "search": "    total = 0\n    for value in values:\n        total += value * value\n    return total\n",
            "replace": "    return sum(value * value for value in values)\n",
        }
    ]
)


def test_engine_smoke(tmp_path: Path) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    program_src = Path("tasks/toy_sum_squares/program.py")
    target = workdir / "program.py"
    target.write_text(program_src.read_text(encoding="utf-8"), encoding="utf-8")

    cfg = {
        "db_path": str(tmp_path / "run.db"),
        "artifacts_root": str(tmp_path / "runs"),
        "workdir": str(workdir),
        "population_size": 1,
        "generations": 2,
        "metrics": {"lints": "maximize"},
        "selection": {"elite": 1, "novel": 0, "young": 0},
        "task": {"description": "demo", "target_file": "program.py"},
        "sampler": {"budget_tokens": 2000, "elites_k": 1, "novel_m": 0, "include_failures": 0},
        "cascade": {
            "max_parallel": 1,
            "cancel_on_fail": False,
            "evaluators": [
                {"name": "LintsEvaluator", "max_lines": 200},
            ],
        },
        "meta_prompt": {"population": 2, "mutation_prob": 0.2, "selection_top_k": 2},
        "archive": {"capacity": 5, "k_novelty": 2, "ageing_threshold": 4},
        "evolution": {"scope": "blocks", "apply_safe_revert": True},
    }

    def fake_llm(prompt: str) -> str:
        return PATCH

    asyncio.run(evolve("run-smoke", cfg, fake_llm))

    from openevolve.db import ProgramDB

    db = ProgramDB(cfg["db_path"])
    cands = db.get_candidates_by_run("run-smoke")
    assert cands
    metrics = db.get_candidate_evals([cand["cand_id"] for cand in cands])
    assert metrics
