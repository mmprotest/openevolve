from openevolve.selection import dominates, novelty_score, pareto_front, update_archive


def test_dominates_and_pareto():
    candidates = [
        {"accuracy": 0.9, "speed": 0.5},
        {"accuracy": 0.85, "speed": 0.7},
        {"accuracy": 0.9, "speed": 0.6},
    ]
    front = pareto_front(candidates, ["accuracy", "speed"])
    assert set(front) == {1, 2}
    assert dominates(candidates[2], candidates[0], ["accuracy", "speed"])


def test_novelty_score_and_archive():
    archive: list[tuple[float, float]] = []
    score_empty = novelty_score((0.0, 0.0), archive)
    assert score_empty == float("inf")

    update_archive(archive, (0.0, 0.0), max_size=5)
    update_archive(archive, (1.0, 1.0), max_size=5)
    score = novelty_score((0.5, 0.5), archive, k=2)
    assert 0 < score < 1

    update_archive(archive, (2.0, 2.0), max_size=2)
    assert len(archive) == 2
