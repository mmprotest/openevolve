"""SQLite-backed persistence for OpenEvolve runs."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Callable, Iterable

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class ProgramDB:
    """Lightweight wrapper around sqlite3 for storing run state."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self._lock:
            with SCHEMA_PATH.open("r", encoding="utf-8") as fh:
                schema_sql = fh.read()
            self._conn.executescript(schema_sql)
            self._conn.commit()

    def upsert_run(self, run_id: str, config: dict) -> None:
        payload = json.dumps(config, sort_keys=True)
        with self._lock:
            self._conn.execute(
                "INSERT INTO runs(run_id, config_json) VALUES(?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET config_json=excluded.config_json",
                (run_id, payload),
            )
            self._conn.commit()

    def insert_candidate(self, run_id: str, cand: dict) -> None:
        parent_ids = cand.get("parent_ids") or []
        if isinstance(parent_ids, (list, tuple)):
            parent_str = ",".join(parent_ids)
        else:
            parent_str = str(parent_ids)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO candidates(
                    cand_id, run_id, parent_ids, meta_prompt_id, filepath, patch,
                    code_snapshot, gen, novelty, age
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cand["cand_id"],
                    run_id,
                    parent_str,
                    cand.get("meta_prompt_id"),
                    cand.get("filepath"),
                    cand.get("patch"),
                    cand.get("code_snapshot"),
                    cand.get("gen", 0),
                    cand.get("novelty", 0.0),
                    cand.get("age", 0),
                ),
            )
            self._conn.commit()

    def insert_evaluations(
        self,
        cand_id: str,
        evals: dict[str, float],
        passed: dict[str, bool],
        cost_ms: dict[str, int],
        error_by_metric: dict[str, str],
    ) -> None:
        rows = []
        for metric, value in evals.items():
            rows.append(
                (
                    cand_id,
                    metric,
                    value,
                    1 if passed.get(metric, False) else 0,
                    int(cost_ms.get(metric, 0)),
                    error_by_metric.get(metric),
                )
            )
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO evaluations(cand_id, metric, value, passed, cost_ms, error)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()

    def _fetchall(self, query: str, params: Iterable) -> list[sqlite3.Row]:
        cur = self._conn.execute(query, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def get_candidates_by_run(self, run_id: str, gen: int | None = None) -> list[dict]:
        params: tuple[object, ...]
        if gen is None:
            query = "SELECT * FROM candidates WHERE run_id = ? ORDER BY created_at"
            params = (run_id,)
        else:
            query = (
                "SELECT * FROM candidates WHERE run_id = ? AND gen = ? "
                "ORDER BY created_at"
            )
            params = (run_id, gen)
        rows = self._fetchall(query, params)
        return [dict(row) for row in rows]

    def _candidate_metrics(self, run_id: str, metrics: list[str]) -> dict[str, dict[str, float]]:
        placeholders = ",".join("?" for _ in metrics)
        query = (
            "SELECT cand_id, metric, value FROM evaluations"
            " WHERE cand_id IN (SELECT cand_id FROM candidates WHERE run_id = ?)"
            f" AND metric IN ({placeholders})"
        )
        params: tuple[object, ...] = (run_id, *metrics)
        cur = self._conn.execute(query, params)
        table: dict[str, dict[str, float]] = {}
        for cand_id, metric, value in cur.fetchall():
            table.setdefault(cand_id, {})[metric] = value
        cur.close()
        return table

    def top_candidates(
        self, run_id: str, k: int, metrics: list[str], minimize: dict[str, bool]
    ) -> list[dict]:
        cands = self.get_candidates_by_run(run_id)
        if not cands:
            return []
        evals = self._candidate_metrics(run_id, metrics)
        scored: list[tuple[float, dict]] = []
        for cand in cands:
            cand_metrics = evals.get(cand["cand_id"], {})
            if not cand_metrics:
                continue
            score = 0.0
            for metric in metrics:
                if metric not in cand_metrics:
                    continue
                value = cand_metrics[metric]
                if minimize.get(metric, False):
                    score -= value
                else:
                    score += value
            scored.append((score, cand))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [cand for _, cand in scored[:k]]

    def diverse_candidates(
        self, run_id: str, k: int, feature_fn: Callable[[dict], set[str]]
    ) -> list[dict]:
        cands = self.get_candidates_by_run(run_id)
        if not cands:
            return []
        selected: list[dict] = []
        seen_features: list[set[str]] = []
        for cand in cands:
            feat = feature_fn(cand)
            if not seen_features:
                selected.append(cand)
                seen_features.append(feat)
                if len(selected) >= k:
                    break
                continue
            distances = [1 - len(feat & prev) / max(len(feat | prev), 1) for prev in seen_features]
            min_distance = min(distances)
            if min_distance > 0.3 or len(selected) < k:
                selected.append(cand)
                seen_features.append(feat)
            if len(selected) >= k:
                break
        return selected[:k]

    def insert_meta_prompt(self, template: str, parents: list[str]) -> str:
        meta_id = str(uuid.uuid4())
        parent_str = ",".join(parents)
        with self._lock:
            self._conn.execute(
                "INSERT INTO meta_prompts(meta_prompt_id, template, parent_ids, last_used)"
                " VALUES(?, ?, ?, CURRENT_TIMESTAMP)",
                (meta_id, template, parent_str),
            )
            self._conn.commit()
        return meta_id

    def update_meta_prompt_fitness(self, meta_prompt_id: str, fitness: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE meta_prompts SET fitness = ?, last_used = CURRENT_TIMESTAMP"
                " WHERE meta_prompt_id = ?",
                (float(fitness), meta_prompt_id),
            )
            self._conn.commit()

    def get_meta_prompts(self, limit: int) -> list[dict]:
        cur = self._conn.execute(
            "SELECT * FROM meta_prompts ORDER BY fitness DESC, last_used DESC LIMIT ?",
            (limit,),
        )
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
        return rows

    def get_run(self, run_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        data = dict(row)
        if data.get("config_json"):
            data["config"] = json.loads(data["config_json"])
        return data

    def get_candidate_evals(self, cand_ids: Iterable[str]) -> dict[str, dict[str, float]]:
        cand_list = list(cand_ids)
        if not cand_list:
            return {}
        placeholders = ",".join("?" for _ in cand_list)
        query = (
            f"SELECT cand_id, metric, value FROM evaluations WHERE cand_id IN ({placeholders})"
        )
        cur = self._conn.execute(query, tuple(cand_list))
        table: dict[str, dict[str, float]] = {}
        for cand_id, metric, value in cur.fetchall():
            table.setdefault(cand_id, {})[metric] = value
        cur.close()
        return table

    def get_candidate(self, cand_id: str) -> dict | None:
        cur = self._conn.execute("SELECT * FROM candidates WHERE cand_id = ?", (cand_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_meta_prompts(self) -> list[dict]:
        cur = self._conn.execute("SELECT * FROM meta_prompts ORDER BY fitness DESC")
        rows = [dict(row) for row in cur.fetchall()]
        cur.close()
        return rows

    def close(self) -> None:
        with self._lock:
            self._conn.close()
