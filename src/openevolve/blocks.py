"""Identify and manipulate EVOLVE blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


BLOCK_START = "# EVOLVE-BLOCK-START"
BLOCK_END = "# EVOLVE-BLOCK-END"


@dataclass(slots=True)
class EvolveBlock:
    name: str
    start_line: int
    end_line: int
    content: str


def extract_blocks(source: str) -> list[EvolveBlock]:
    """Return all evolve blocks in the provided source."""

    lines = source.splitlines()
    blocks: list[EvolveBlock] = []
    active_start: int | None = None
    block_lines: list[str] = []
    block_name = ""

    for idx, line in enumerate(lines):
        if line.strip().startswith(BLOCK_START):
            active_start = idx
            block_lines = []
            parts = line.split(maxsplit=1)
            block_name = parts[1] if len(parts) > 1 else f"block_{len(blocks)}"
            continue
        if line.strip().startswith(BLOCK_END) and active_start is not None:
            content = "\n".join(block_lines)
            blocks.append(
                EvolveBlock(
                    name=block_name,
                    start_line=active_start,
                    end_line=idx,
                    content=content,
                )
            )
            active_start = None
            block_lines = []
            continue
        if active_start is not None:
            block_lines.append(line)

    return blocks


def replace_block(source: str, block: EvolveBlock, new_content: str) -> str:
    """Replace a block's content with new content."""

    lines = source.splitlines()
    head = lines[: block.start_line + 1]
    tail = lines[block.end_line :]
    replacement = new_content.rstrip("\n").splitlines()
    combined = head + replacement + tail
    return "\n".join(combined) + "\n"
