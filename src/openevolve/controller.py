"""High level orchestration loop (simplified)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .blocks import extract_blocks, replace_block
from .config import load_settings
from .diffs import apply_diff, parse_diff
from .llm_client import LLMClientProtocol, build_default_client
from .prompts import build_prompt, validate_model_response


@dataclass(slots=True)
class EvolutionTask:
    name: str
    description: str
    program_path: Path
    evaluation: Callable[[str], Mapping[str, float]]


class EvolutionController:
    """Simplified controller orchestrating mutation and evaluation."""

    def __init__(self, client: LLMClientProtocol | None = None) -> None:
        self.settings = load_settings()
        self.client: LLMClientProtocol = client or build_default_client()

    async def evolve_once(self, task: EvolutionTask) -> Mapping[str, float]:
        source = task.program_path.read_text()
        blocks = extract_blocks(source)
        if not blocks:
            raise RuntimeError("No EVOLVE blocks found in program")
        block = blocks[0]

        prompt = build_prompt(task_description=task.description, block_source=block.content)
        result = await self.client.generate(prompt=prompt, system="You mutate code blocks")

        accepted_metrics: dict[str, float] | None = None
        for diff_text in result.candidates:
            try:
                validate_model_response(diff_text)
                hunks = parse_diff(diff_text)
                new_source = apply_diff(block.content, hunks)
            except ValueError:
                continue

            updated_program = replace_block(source, block, new_source)
            metrics = dict(task.evaluation(updated_program))
            if metrics:
                task.program_path.write_text(updated_program)
                accepted_metrics = metrics
                break
        if accepted_metrics is None:
            raise RuntimeError("No candidate diff produced an improved program")
        return accepted_metrics
