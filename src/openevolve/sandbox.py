"""Lightweight sandbox execution helpers."""

from __future__ import annotations

import contextlib
import runpy
import tempfile
from pathlib import Path
from typing import Any, Mapping


class SandboxExecutionError(RuntimeError):
    pass


def run_in_sandbox(source: str, globals_dict: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    """Execute *source* in a temporary module context."""

    globals_dict = dict(globals_dict or {})
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "candidate.py"
        script_path.write_text(source)
        try:
            module_globals = runpy.run_path(str(script_path), init_globals=globals_dict)
        except Exception as exc:  # noqa: BLE001
            raise SandboxExecutionError(str(exc)) from exc
    return module_globals
