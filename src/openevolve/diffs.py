"""Diff parsing and application helpers."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from typing import Iterable, Sequence


DIFF_BLOCK_RE = re.compile(
    r"<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE(?:\n|$)",
    re.DOTALL,
)


@dataclass(slots=True)
class DiffHunk:
    """Represents a SEARCH/REPLACE hunk."""

    search: str
    replace: str

    def apply(self, source: str) -> str:
        """Apply the hunk to *source* returning the transformed text."""

        if self.search not in source:
            raise ValueError("Search segment not found in source")
        return source.replace(self.search, self.replace, 1)


def parse_diff(diff_text: str) -> list[DiffHunk]:
    """Parse diff text into structured hunks."""

    diff_text = diff_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if diff_text.startswith("```"):
        lines = diff_text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        diff_text = "\n".join(lines).strip()

    if not diff_text:
        raise ValueError("Empty diff text")

    matches = list(DIFF_BLOCK_RE.finditer(diff_text))
    if not matches:
        raise ValueError("Diff text does not match SEARCH/REPLACE format")

    hunks: list[DiffHunk] = []
    for match in matches:
        search = match.group("search")
        replace = match.group("replace")
        hunks.append(DiffHunk(search=search, replace=replace))
    return hunks


def apply_diff(source: str, hunks: Sequence[DiffHunk]) -> str:
    """Apply multiple hunks sequentially."""

    result = source
    for hunk in hunks:
        result = hunk.apply(result)
    return result


def is_valid_diff(diff_text: str) -> bool:
    try:
        parse_diff(diff_text)
    except ValueError:
        return False
    return True
