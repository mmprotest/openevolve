from __future__ import annotations

from openevolve.selection import Archive, jaccard_novelty, pareto_rank


def test_pareto_rank_and_archive():
    candidates = [
        {"cand_id": "a", "gen": 0, "code_snapshot": "def f():\n    return 1\n"},
        {"cand_id": "b", "gen": 0, "code_snapshot": "def f():\n    return 2\n"},
        {"cand_id": "c", "gen": 1, "code_snapshot": "def g():\n    return 3\n"},
    ]
    evals = {
        "a": {"acc": 0.8, "time": 100},
        "b": {"acc": 0.9, "time": 120},
        "c": {"acc": 0.85, "time": 90},
    }
    metrics = {"acc": True, "time": False}

    ranks = pareto_rank(candidates, evals, metrics)
    assert ranks["c"] == 0

    archive = Archive(capacity=3, metrics=metrics, k_novelty=2)
    archive.update(candidates, evals, current_gen=2)
    mixture = archive.sample_mixture(1, 1, 1)
    assert "c" in mixture


def test_jaccard_novelty():
    features = {
        "a": {"foo", "Bar"},
        "b": {"foo", "Baz"},
        "c": {"alpha", "beta"},
    }
    novelty = jaccard_novelty(features, 2)
    assert novelty["c"] > novelty["a"]
