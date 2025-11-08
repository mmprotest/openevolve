"""Prompt assembly utilities."""

from __future__ import annotations

import textwrap
from collections import deque
from typing import Iterable

from .db import ProgramDB
from .selection import Archive


def _approx_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _format_candidate_summary(cand: dict, metrics: dict[str, float]) -> str:
    metrics_str = ", ".join(f"{k}={v:.3f}" for k, v in sorted(metrics.items())) or "no metrics"
    snippet = cand.get("code_snapshot", "")
    snippet = "\n".join(snippet.splitlines()[:12])
    return textwrap.dedent(
        f"""
        Candidate {cand['cand_id']} (gen {cand.get('gen', '?')}, novelty={cand.get('novelty', 0):.3f}):
        Metrics: {metrics_str}
        Diff:
        {cand.get('patch', '').strip() or '<empty>'}
        Snapshot:
        {snippet}
        """
    ).strip()


def _format_failure_summary(cand: dict) -> str:
    patch = cand.get("patch", "").strip() or "<empty>"
    error = cand.get("error", "unknown")
    return textwrap.dedent(
        f"""
        Failed Candidate {cand['cand_id']}:
        Patch:
        {patch}
        Error: {error}
        """
    ).strip()


def build_prompt(
    run_id: str,
    db: ProgramDB,
    budget_tokens: int,
    task_desc: str,
    target_file: str,
    evolve_blocks: list[tuple[int, int]],
    metrics: list[str],
    sampler_cfg: dict,
    meta_prompt_template: str,
) -> str:
    """Construct a long-context prompt describing run context and expectations."""

    all_candidates = db.get_candidates_by_run(run_id)
    minimize = {m: False for m in metrics}
    elites = db.top_candidates(
        run_id,
        sampler_cfg.get("elites_k", 4),
        metrics,
        minimize,
    )

    archive = Archive(capacity=256, metrics={m: True for m in metrics})
    evals = db.get_candidate_evals(cand["cand_id"] for cand in all_candidates)
    archive.update(all_candidates, evals)
    novelty_ids = archive.sample_mixture(0, sampler_cfg.get("novel_m", 4), 0)
    novelty_lookup = {cand["cand_id"]: cand for cand in all_candidates}
    novelty = [novelty_lookup[i] for i in novelty_ids if i in novelty_lookup]

    failure_count = sampler_cfg.get("include_failures", 2)
    failures: list[dict] = []
    if failure_count:
        cur = db._conn.execute(
            "SELECT c.cand_id, c.patch, e.error FROM candidates c"
            " JOIN evaluations e ON e.cand_id = c.cand_id"
            " WHERE e.passed = 0 ORDER BY e.created_at DESC LIMIT ?",
            (failure_count,),
        )
        for row in cur.fetchall():
            failures.append({"cand_id": row["cand_id"], "patch": row["patch"], "error": row["error"]})
        cur.close()

    sections = deque()
    sections.append(
        textwrap.dedent(
            f"""
            You are improving the program `{target_file}` for run `{run_id}`.
            Follow the meta-instruction template below when producing changes.
            Task description: {task_desc}
            Metrics optimised: {', '.join(metrics) or 'n/a'}
            Target EVOLVE blocks: {evolve_blocks or 'entire file'}
            """
        ).strip()
    )
    sections.append(meta_prompt_template.strip())

    for cand in elites:
        metrics_table = evals.get(cand["cand_id"], {})
        sections.append(_format_candidate_summary(cand, metrics_table))

    for cand in novelty:
        metrics_table = evals.get(cand["cand_id"], {})
        sections.append("[Novel exemplar]\n" + _format_candidate_summary(cand, metrics_table))

    for cand in failures:
        sections.append(_format_failure_summary(cand))

    sections.append(
        """When returning a patch, prefer JSON with entries {"block_id", "search", "replace"}.
If a unified diff is necessary, ensure it applies cleanly via `patch -p0`.
Respond with only the diff instructions."""
    )

    tokens = 0
    kept = []
    while sections and tokens < budget_tokens:
        piece = sections.popleft()
        tokens += _approx_tokens(piece)
        if tokens <= budget_tokens:
            kept.append(piece)
        else:
            break

    prompt = "\n\n".join(kept)
    return prompt
