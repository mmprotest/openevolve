"""Run the algorithmic optimisation demo task end-to-end."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for entry in (ROOT, SRC):
    entry_str = str(entry)
    if entry_str not in sys.path:
        sys.path.insert(0, entry_str)

from tasks.algorithmic_optimization.evaluate import evaluate

PROGRAM_PATH = (
    ROOT
    / "tasks"
    / "algorithmic_optimization"
    / "program.py"
)

BASELINE_BLOCK = """    arr = list(values)\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr\n"""

IMPROVED_BLOCK = """    arr = list(values)\n    for idx in range(1, len(arr)):\n        value = arr[idx]\n        pos = idx - 1\n        while pos >= 0 and arr[pos] > value:\n            arr[pos + 1] = arr[pos]\n            pos -= 1\n        arr[pos + 1] = value\n    return arr\n"""


def main() -> None:
    baseline_source = PROGRAM_PATH.read_text(encoding="utf-8")
    baseline_metrics = evaluate(baseline_source)

    improved_source = baseline_source.replace(BASELINE_BLOCK, IMPROVED_BLOCK)
    improved_metrics = evaluate(improved_source)

    print("Baseline bubble sort metrics:")
    for name, value in baseline_metrics.items():
        print(f"  {name:>12}: {value:.4f}")

    print("\nInsertion-sort inspired metrics:")
    for name, value in improved_metrics.items():
        print(f"  {name:>12}: {value:.4f}")

    print("\nPatch preview:")
    base_lines = BASELINE_BLOCK.splitlines()
    improved_lines = IMPROVED_BLOCK.splitlines()
    max_len = max(len(base_lines), len(improved_lines))
    base_lines.extend([""] * (max_len - len(base_lines)))
    improved_lines.extend([""] * (max_len - len(improved_lines)))
    for before, after in zip(base_lines, improved_lines):
        print(f"- {before}")
        print(f"+ {after}")


if __name__ == "__main__":
    main()
