"""Command line interface for OpenEvolve."""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from .config import load_config
from .db import ProgramDB
from .engine import evolve
from .llm_client import OpenEvolveClient
from .utils import ensure_event_loop
from .viz import plot_pareto

logger = logging.getLogger(__name__)


def _default_llm_call(prompt: str) -> str:  # pragma: no cover - interactive usage
    raise RuntimeError("No LLM backend configured. Provide an llm_call implementation.")


def _resolve_llm(cfg: dict[str, Any]) -> Callable[[str], str]:
    llm_cfg = cfg.get("llm", {})
    mode = llm_cfg.get("mode", "noop")
    if mode == "noop":
        return lambda prompt: ""
    if mode == "echo":
        return lambda prompt: llm_cfg.get("response", "")
    if mode == "file":
        path = Path(llm_cfg["path"]).expanduser()
        return lambda prompt: path.read_text(encoding="utf-8")
    if mode == "openai":
        client = OpenEvolveClient(
            api_key=llm_cfg.get("api_key"),
            base_url=llm_cfg.get("base_url"),
            default_model=llm_cfg.get("model"),
            timeout=float(llm_cfg.get("timeout", 60.0)),
            max_retries=int(llm_cfg.get("max_retries", 3)),
        )
        system_prompt = llm_cfg.get(
            "system_prompt",
            "You are an expert software engineer evolving code through structured diffs.",
        )
        temperature = float(llm_cfg.get("temperature", 0.7))
        n = int(llm_cfg.get("n", 1))

        def _call(prompt: str) -> str:
            result = client.generate_sync(
                prompt=prompt,
                system=system_prompt,
                n=n,
                temperature=temperature,
            )
            return result.candidates[0] if result.candidates else ""

        def _close_client() -> None:
            loop = ensure_event_loop()
            loop.run_until_complete(client.aclose())

        atexit.register(_close_client)
        return _call
    return _default_llm_call


def cmd_init_db(args: argparse.Namespace) -> None:
    db = ProgramDB(args.db)
    db.ensure_schema()
    db.close()
    print(f"Initialised database at {args.db}")


def cmd_run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config, overrides={"dry_run": args.dry_run})
    run_id = args.run_id or str(uuid.uuid4())
    cfg["db_path"] = args.db or cfg.get("db_path")
    cfg["workdir"] = args.workdir
    llm_call = _resolve_llm(cfg)
    asyncio.run(evolve(run_id, cfg, llm_call))


def cmd_resume(args: argparse.Namespace) -> None:
    db = ProgramDB(args.db)
    record = db.get_run(args.run_id)
    if not record:
        raise SystemExit(f"Run {args.run_id} not found")
    cfg = record.get("config", {})
    cfg["db_path"] = args.db
    cfg["dry_run"] = args.dry_run
    llm_call = _resolve_llm(cfg)
    asyncio.run(evolve(args.run_id, cfg, llm_call))


def cmd_inspect(args: argparse.Namespace) -> None:
    db = ProgramDB(args.db)
    rows = db.get_candidates_by_run(args.run_id)
    metrics = db.get_candidate_evals([row["cand_id"] for row in rows])
    rows.sort(key=lambda row: -row.get("novelty", 0.0))
    for row in rows[: args.top]:
        metrics_str = json.dumps(metrics.get(row["cand_id"], {}))
        print(f"{row['cand_id']} gen={row.get('gen')} novelty={row.get('novelty', 0):.3f} metrics={metrics_str}")


def cmd_export_archive(args: argparse.Namespace) -> None:
    db = ProgramDB(args.db)
    rows = db.get_candidates_by_run(args.run_id)
    metrics = db.get_candidate_evals([row["cand_id"] for row in rows])
    payload = []
    for row in rows:
        payload.append({"candidate": row, "metrics": metrics.get(row["cand_id"], {})})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.out).open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"Archive exported to {args.out}")


def cmd_viz(args: argparse.Namespace) -> None:
    db = ProgramDB(args.db)
    metrics = [m.strip() for m in args.metric_axes.split(",") if m.strip()]
    plot_pareto(args.run_id, db, metrics, Path(args.out))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openevolve", description="OpenEvolve command line")
    parser.add_argument("--db", default=".openevolve/openevolve.db", help="Database path")
    parser.add_argument("--workdir", default=".", help="Workspace directory")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Initialise database")
    p_init.set_defaults(func=cmd_init_db)

    p_run = sub.add_parser("run", help="Start a new run")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--run-id")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser("resume", help="Resume a run")
    p_resume.add_argument("--run-id", required=True)
    p_resume.add_argument("--dry-run", action="store_true")
    p_resume.set_defaults(func=cmd_resume)

    p_inspect = sub.add_parser("inspect", help="Inspect top candidates")
    p_inspect.add_argument("--run-id", required=True)
    p_inspect.add_argument("--top", type=int, default=10)
    p_inspect.set_defaults(func=cmd_inspect)

    p_export = sub.add_parser("export-archive", help="Export archive as JSON")
    p_export.add_argument("--run-id", required=True)
    p_export.add_argument("--out", required=True)
    p_export.set_defaults(func=cmd_export_archive)

    p_viz = sub.add_parser("viz", help="Plot Pareto fronts")
    p_viz.add_argument("--run-id", required=True)
    p_viz.add_argument("--metric-axes", required=True)
    p_viz.add_argument("--out", default="artifacts/pareto.png")
    p_viz.set_defaults(func=cmd_viz)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
