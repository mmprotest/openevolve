from __future__ import annotations

import json
from pathlib import Path

from openevolve.db import ProgramDB


def test_program_db_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "run.db"
    db = ProgramDB(str(db_path))
    db.upsert_run("run1", {"foo": "bar"})

    cand = {
        "cand_id": "c1",
        "parent_ids": ["p1"],
        "meta_prompt_id": "m1",
        "filepath": "demo.py",
        "patch": "[]",
        "code_snapshot": "print('hi')\n",
        "gen": 0,
        "novelty": 0.1,
        "age": 0,
    }
    db.insert_candidate("run1", cand)
    db.insert_evaluations("c1", {"accuracy": 1.0}, {"accuracy": True}, {"accuracy": 10}, {"accuracy": None})

    rows = db.get_candidates_by_run("run1")
    assert rows[0]["cand_id"] == "c1"

    metrics = db.get_candidate_evals(["c1"])
    assert metrics["c1"]["accuracy"] == 1.0

    meta_id = db.insert_meta_prompt("template", [])
    db.update_meta_prompt_fitness(meta_id, 0.9)
    prompts = db.get_meta_prompts(5)
    assert prompts[0]["meta_prompt_id"] == meta_id

    run_record = db.get_run("run1")
    assert json.loads(run_record["config_json"])["foo"] == "bar"

    db.close()
