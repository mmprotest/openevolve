from openevolve.diffs import DiffHunk, apply_diff, is_valid_diff, parse_diff


def test_parse_diff_single_hunk():
    diff_text = """<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>> REPLACE"""
    hunks = parse_diff(diff_text)
    assert len(hunks) == 1
    assert hunks[0].search == "foo"
    assert hunks[0].replace == "bar"


def test_apply_diff():
    source = "foo = 1\n"
    hunk = DiffHunk(search="foo", replace="bar")
    updated = apply_diff(source, [hunk])
    assert "bar = 1" in updated


def test_is_valid_diff():
    assert is_valid_diff("""<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>> REPLACE""")
    assert not is_valid_diff("invalid format")
