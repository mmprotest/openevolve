"""Export archive entries for a run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openevolve.db import ProgramDB


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenEvolve archive")
    parser.add_argument("run_id")
    parser.add_argument("out")
    parser.add_argument("--db", default=".openevolve/openevolve.db")
    args = parser.parse_args()

    db = ProgramDB(args.db)
    candidates = db.get_candidates_by_run(args.run_id)
    metrics = db.get_candidate_evals([cand["cand_id"] for cand in candidates])
    payload = []
    for cand in candidates:
        payload.append({"candidate": cand, "metrics": metrics.get(cand["cand_id"], {})})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


if __name__ == "__main__":  # pragma: no cover
    main()
