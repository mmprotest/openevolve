"""Selection utilities for evolutionary search."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence


def dominates(a: dict[str, float], b: dict[str, float], objectives: Sequence[str]) -> bool:
    """Return True if metric dict *a* dominates *b* for objectives (higher is better)."""

    better_or_equal = True
    strictly_better = False
    for objective in objectives:
        a_val = a.get(objective)
        b_val = b.get(objective)
        if a_val is None or b_val is None:
            raise KeyError(f"Missing objective '{objective}' in candidate metrics")
        if a_val < b_val:
            better_or_equal = False
            break
        if a_val > b_val:
            strictly_better = True
    return better_or_equal and strictly_better


def pareto_front(candidates: Sequence[dict[str, float]], objectives: Sequence[str]) -> list[int]:
    """Return indices of Pareto optimal candidates."""

    front: list[int] = []
    for idx, metrics in enumerate(candidates):
        dominated = False
        for jdx, other in enumerate(candidates):
            if jdx == idx:
                continue
            if dominates(other, metrics, objectives):
                dominated = True
                break
        if not dominated:
            front.append(idx)
    return front


def euclidean_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))


def novelty_score(
    descriptor: Sequence[float],
    archive: Sequence[Sequence[float]],
    *,
    k: int = 5,
) -> float:
    """Compute novelty as mean distance to k nearest neighbours in archive."""

    if not archive:
        return float("inf")

    distances = sorted(euclidean_distance(descriptor, other) for other in archive)
    sample = distances[: max(1, min(k, len(distances)))]
    return sum(sample) / len(sample)


def update_archive(
    archive: list[Sequence[float]],
    descriptor: Sequence[float],
    *,
    max_size: int,
) -> None:
    """Append descriptor to archive with bounded size (FIFO)."""

    archive.append(tuple(descriptor))
    if len(archive) > max_size:
        del archive[0 : len(archive) - max_size]


def pareto_rank(
    cands: list[dict],
    evals: dict[str, dict[str, float]],
    metrics: dict[str, bool],
) -> dict[str, int]:
    """Return Pareto rank per candidate (0 is best)."""

    normalized: dict[str, list[float]] = {}
    for cand in cands:
        cand_id = cand["cand_id"]
        measurements = evals.get(cand_id)
        if not measurements:
            continue
        vec: list[float] = []
        valid = True
        for metric, maximize in metrics.items():
            if metric not in measurements:
                valid = False
                break
            value = measurements[metric]
            vec.append(value if maximize else -value)
        if valid:
            normalized[cand_id] = vec

    ranks: dict[str, int] = {}
    remaining = dict(normalized)
    current_rank = 0
    while remaining:
        front: list[str] = []
        ids = list(remaining)
        for cand_id in ids:
            vec = remaining[cand_id]
            dominated = False
            for other_id, other_vec in remaining.items():
                if cand_id == other_id:
                    continue
                if _dominates_vec(other_vec, vec):
                    dominated = True
                    break
            if not dominated:
                front.append(cand_id)
        for cand_id in front:
            ranks[cand_id] = current_rank
            remaining.pop(cand_id, None)
        current_rank += 1
    return ranks


def _dominates_vec(a: Sequence[float], b: Sequence[float]) -> bool:
    return all(x >= y for x, y in zip(a, b)) and any(x > y for x, y in zip(a, b))


def jaccard_novelty(features_by_cand: dict[str, set[str]], k: int) -> dict[str, float]:
    """Compute novelty based on Jaccard distance between feature sets."""

    ids = list(features_by_cand)
    novelty: dict[str, float] = {}
    for i, cand_id in enumerate(ids):
        features = features_by_cand[cand_id]
        distances: list[float] = []
        for j, other_id in enumerate(ids):
            if i == j:
                continue
            other = features_by_cand[other_id]
            union = features | other
            if not union:
                distances.append(0.0)
            else:
                distances.append(1.0 - len(features & other) / len(union))
        if not distances:
            novelty[cand_id] = 1.0
        else:
            distances.sort(reverse=True)
            sample = distances[: max(1, min(k, len(distances)))]
            novelty[cand_id] = sum(sample) / len(sample)
    return novelty


def _extract_features_from_code(code: str) -> set[str]:
    features: set[str] = set()
    if not code:
        return features
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return features
    for node in ast.walk(tree):
        features.add(type(node).__name__)
        for field in getattr(node, "_fields", []):
            value = getattr(node, field, None)
            if isinstance(value, str) and value.isidentifier():
                features.add(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.isidentifier():
                        features.add(item)
    return features


@dataclass
class ArchiveEntry:
    cand_id: str
    metrics: dict[str, float]
    code_snapshot: str
    age: int = 0
    novelty: float = 0.0
    rank: int = 0


@dataclass
class Archive:
    capacity: int
    metrics: dict[str, bool]
    k_novelty: int = 10
    entries: dict[str, ArchiveEntry] = field(default_factory=dict)

    def update(
        self,
        candidates: list[dict],
        eval_table: dict[str, dict[str, float]],
        current_gen: int | None = None,
    ) -> None:
        """Update archive with new candidate information."""

        relevant = [cand for cand in candidates if cand["cand_id"] in eval_table]
        ranks = pareto_rank(relevant, eval_table, self.metrics)
        features_by_cand: dict[str, set[str]] = {}
        for cand in relevant:
            cand_id = cand["cand_id"]
            metrics = eval_table[cand_id]
            age = (current_gen - int(cand.get("gen", 0))) if current_gen is not None else cand.get("age", 0)
            entry = ArchiveEntry(
                cand_id=cand_id,
                metrics=metrics,
                code_snapshot=cand.get("code_snapshot", ""),
                age=max(0, age),
                novelty=cand.get("novelty", 0.0),
                rank=ranks.get(cand_id, 0),
            )
            self.entries[cand_id] = entry
            features_by_cand[cand_id] = _extract_features_from_code(entry.code_snapshot)

        novelty_scores = jaccard_novelty(features_by_cand, self.k_novelty)
        for cand_id, score in novelty_scores.items():
            if cand_id in self.entries:
                self.entries[cand_id].novelty = score

        if len(self.entries) > self.capacity:
            self._truncate()

    def _truncate(self) -> None:
        ordered = sorted(
            self.entries.values(),
            key=lambda e: (e.rank, -e.novelty, e.age),
        )
        keep = ordered[: self.capacity]
        self.entries = {entry.cand_id: entry for entry in keep}

    def pareto_front(self) -> list[str]:
        if not self.entries:
            return []
        best_rank = min(entry.rank for entry in self.entries.values())
        return [entry.cand_id for entry in self.entries.values() if entry.rank == best_rank]

    def sample_mixture(self, n_elite: int, n_novel: int, n_young: int) -> list[str]:
        ordered_elites = sorted(self.entries.values(), key=lambda e: e.rank)
        ordered_novel = sorted(self.entries.values(), key=lambda e: e.novelty, reverse=True)
        ordered_young = sorted(self.entries.values(), key=lambda e: e.age)

        selected: list[str] = []

        for entry in ordered_elites[:n_elite]:
            selected.append(entry.cand_id)
        for entry in ordered_novel:
            if len(selected) >= n_elite + n_novel:
                break
            if entry.cand_id not in selected:
                selected.append(entry.cand_id)
        for entry in ordered_young:
            if len(selected) >= n_elite + n_novel + n_young:
                break
            if entry.cand_id not in selected:
                selected.append(entry.cand_id)

        return selected
