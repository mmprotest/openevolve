"""Visualization helpers for Pareto fronts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:  # pragma: no cover - optional dependency
    import matplotlib.pyplot as plt
except Exception as exc:  # pragma: no cover - optional
    plt = None

from .db import ProgramDB


def plot_pareto(run_id: str, db: ProgramDB, metrics: list[str], out_path: Path) -> None:
    if plt is None:
        raise RuntimeError("matplotlib is required for visualisation")
    candidates = db.get_candidates_by_run(run_id)
    evals = db.get_candidate_evals([cand["cand_id"] for cand in candidates])
    if len(metrics) < 2:
        raise ValueError("Provide at least two metrics for plotting")
    x_metric, y_metric = metrics[:2]
    xs = []
    ys = []
    for cand in candidates:
        metrics_values = evals.get(cand["cand_id"], {})
        if x_metric in metrics_values and y_metric in metrics_values:
            xs.append(metrics_values[x_metric])
            ys.append(metrics_values[y_metric])
    if not xs:
        raise RuntimeError("No data to plot")
    plt.figure(figsize=(6, 4))
    plt.scatter(xs, ys, c="blue", alpha=0.6)
    plt.xlabel(x_metric)
    plt.ylabel(y_metric)
    plt.title(f"Run {run_id} Pareto scatter")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()
