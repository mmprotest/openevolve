"""Tests for EVOLVE block extraction and replacement helpers."""

from __future__ import annotations

from textwrap import dedent

from openevolve.blocks import extract_blocks, replace_block


def test_extract_blocks_records_indent_and_normalized_content() -> None:
    source = dedent(
        """
        def wrapper():
            # EVOLVE-BLOCK-START sample
            value = 1
            return value
            # EVOLVE-BLOCK-END
        """
    ).lstrip()

    blocks = extract_blocks(source)
    assert len(blocks) == 1
    block = blocks[0]
    assert block.indent == "    "
    assert block.content.splitlines()[0].startswith("    ")
    assert block.normalized_content == "value = 1\nreturn value"


def test_replace_block_reindents_new_content() -> None:
    source = dedent(
        """
        def wrapper():
            # EVOLVE-BLOCK-START sample
            value = 1
            return value
            # EVOLVE-BLOCK-END
        """
    ).lstrip()

    blocks = extract_blocks(source)
    block = blocks[0]
    replacement = "return sorted(values)\n"

    updated = replace_block(source, block, replacement)

    expected = dedent(
        """
        def wrapper():
            # EVOLVE-BLOCK-START sample
            return sorted(values)
            # EVOLVE-BLOCK-END
        """
    ).lstrip()
    if not expected.endswith("\n"):
        expected += "\n"

    assert updated == expected
