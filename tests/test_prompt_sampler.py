from __future__ import annotations

from pathlib import Path

from openevolve.db import ProgramDB
from openevolve.prompt_sampler import build_prompt


def test_prompt_sampler_budget(tmp_path: Path) -> None:
    db = ProgramDB(str(tmp_path / "db.sqlite"))
    db.upsert_run("run", {})
    for idx in range(3):
        cand_id = f"c{idx}"
        db.insert_candidate(
            "run",
            {
                "cand_id": cand_id,
                "parent_ids": [],
                "meta_prompt_id": "m1",
                "filepath": "demo.py",
                "patch": f"patch {idx}",
                "code_snapshot": "def demo():\n    return 1\n",
                "gen": idx,
            },
        )
        db.insert_evaluations(
            cand_id,
            {"accuracy": 0.8 + idx * 0.05},
            {"accuracy": True},
            {"accuracy": 10},
            {"accuracy": None},
        )
    prompt = build_prompt(
        run_id="run",
        db=db,
        budget_tokens=50,
        task_desc="demo task",
        target_file="demo.py",
        evolve_blocks=[(0, 1)],
        metrics=["accuracy"],
        sampler_cfg={"elites_k": 2, "novel_m": 1, "include_failures": 0},
        meta_prompt_template="Follow instructions strictly.",
    )
    assert "demo task" in prompt
    assert len(prompt.split()) <= 60
