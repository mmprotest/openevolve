from tasks.toy_sum_squares.program import sum_of_squares


def test_sum_of_squares():
    assert sum_of_squares([1, 2, 3]) == 14
    assert sum_of_squares([0, -1, 5]) == 26
