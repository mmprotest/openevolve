from tasks.speed_sort.program import core_algorithm


def test_core_algorithm():
    assert core_algorithm([3, 2, 1]) == [1, 2, 3]
    assert core_algorithm([]) == []
