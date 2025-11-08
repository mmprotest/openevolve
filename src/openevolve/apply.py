"""Utilities to apply candidate patches safely."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .blocks import EvolveBlock, extract_blocks, replace_block

logger = logging.getLogger(__name__)


class ApplyError(RuntimeError):
    pass


@dataclass(slots=True)
class ApplyOutcome:
    success: bool
    new_source: str | None
    error: str | None = None


def load_blocks(path: Path) -> list[EvolveBlock]:
    source = path.read_text(encoding="utf-8")
    return extract_blocks(source)


def parse_patch(patch: str) -> tuple[str, object]:
    try:
        data = json.loads(patch)
    except json.JSONDecodeError:
        return "unified", patch
    if isinstance(data, dict) and "diff" in data:
        return data.get("format", "json"), data["diff"]
    return "json", data


def _apply_json_patch(
    source: str,
    diff: list[dict],
    blocks: dict[str, EvolveBlock],
    scope: str,
) -> str:
    updated = source
    for entry in diff:
        block_id = entry.get("block_id")
        search = entry.get("search", "")
        replace = entry.get("replace", "")
        if block_id:
            if scope == "blocks" and block_id not in blocks:
                raise ApplyError(f"Block {block_id} not found in file")
            block = blocks.get(block_id)
            if block is None:
                raise ApplyError(f"Unknown block {block_id}")
            content = block.content
            if search and search not in content:
                if content.strip() == search.strip():
                    new_content = replace
                else:
                    raise ApplyError(f"Search text not found in block {block_id}")
            else:
                new_content = content.replace(search, replace, 1) if search else replace
            updated = replace_block(updated, block, new_content)
            blocks = {b.name: b for b in extract_blocks(updated)}
        else:
            if scope == "blocks":
                raise ApplyError("Whole-file edit attempted in block mode")
            if search and search not in updated:
                raise ApplyError("Search text not present in file")
            updated = updated.replace(search, replace, 1) if search else replace
    return updated


def _apply_unified_diff(source: str, diff: str) -> str:
    lines = source.splitlines()
    result: list[str] = []
    idx = 0
    diff_lines = diff.splitlines()
    for line in diff_lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            hunk = line.split()[1]
            start = int(hunk.split(",")[0][1:]) - 1
            while idx < start:
                result.append(lines[idx])
                idx += 1
            continue
        if line.startswith("-"):
            idx += 1
        elif line.startswith("+"):
            result.append(line[1:])
        else:
            if idx < len(lines):
                result.append(lines[idx])
                idx += 1
    result.extend(lines[idx:])
    trailing_newline = "\n" if source.endswith("\n") else ""
    return "\n".join(result) + trailing_newline


def apply_patch(
    file_path: Path,
    patch: str,
    scope: str = "blocks",
) -> ApplyOutcome:
    """Apply patch to file respecting scope."""

    source = file_path.read_text(encoding="utf-8")
    blocks = {}
    for block in extract_blocks(source):
        blocks[block.name] = block
        key = block.name.split()[-1]
        blocks[key] = block
    fmt, payload = parse_patch(patch)
    try:
        if fmt == "json":
            if not isinstance(payload, list):
                raise ApplyError("JSON diff must be a list of operations")
            updated = _apply_json_patch(source, payload, blocks, scope)
        else:
            updated = _apply_unified_diff(source, str(payload))
    except ApplyError as exc:
        logger.warning("apply failure", exc_info=exc)
        return ApplyOutcome(success=False, new_source=None, error=str(exc))
    return ApplyOutcome(success=True, new_source=updated)


def write_if_changed(path: Path, new_source: str) -> None:
    path.write_text(new_source, encoding="utf-8")
