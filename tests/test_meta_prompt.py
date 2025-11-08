from __future__ import annotations

from pathlib import Path

from openevolve.db import ProgramDB
from openevolve.meta_prompt import evolve_meta_prompts, mutate_meta_prompt, seed_meta_prompts, select_meta_prompts


def test_meta_prompt_lifecycle(tmp_path: Path) -> None:
    db = ProgramDB(str(tmp_path / "db.sqlite"))
    ids = seed_meta_prompts(db)
    assert ids
    prompts = select_meta_prompts(db, 2)
    assert len(prompts) == 2

    mutated = mutate_meta_prompt(prompts[0]["template"])
    assert mutated != ""

    cand_id = "cand"
    db.insert_candidate(
        "run",
        {
            "cand_id": cand_id,
            "parent_ids": [],
            "meta_prompt_id": prompts[0]["meta_prompt_id"],
            "filepath": "demo.py",
            "patch": "[]",
            "code_snapshot": "print('x')\n",
            "gen": 0,
        },
    )
    db.insert_evaluations(cand_id, {"score": 1.0}, {"score": True}, {"score": 10}, {"score": None})
    evolve_meta_prompts(db, {prompts[0]["meta_prompt_id"]: [cand_id]})
    updated = db.get_meta_prompts(1)[0]
    assert updated["fitness"] > 0
