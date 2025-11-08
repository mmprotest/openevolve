"""High level orchestration loop (simplified)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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

    DEFAULT_SYSTEM_PROMPT = "You mutate code blocks"

    def __init__(
        self,
        client: LLMClientProtocol | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        candidates: int = 1,
        max_rounds: int = 1,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        fail_on_no_candidate: bool = False,
    ) -> None:
        self.settings = load_settings()
        self.client: LLMClientProtocol = client or build_default_client()
        self._model = model
        self._temperature = temperature
        self._candidates = max(1, candidates)
        self._max_rounds = max(1, max_rounds)
        self._system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self._fail_on_no_candidate = fail_on_no_candidate

    async def evolve_once(
        self,
        task: EvolutionTask,
        *,
        model: str | None = None,
        temperature: float | None = None,
        candidates: int | None = None,
        max_rounds: int | None = None,
        system_prompt: str | None = None,
        extra_messages: Sequence[dict[str, Any]] | None = None,
        fail_on_no_candidate: bool | None = None,
    ) -> Mapping[str, float]:
        source = task.program_path.read_text()
        blocks = extract_blocks(source)
        if not blocks:
            raise RuntimeError("No EVOLVE blocks found in program")
        block = blocks[0]

        prompt = build_prompt(task_description=task.description, block_source=block.content)

        baseline_metrics = dict(task.evaluation(source))
        accepted_metrics: dict[str, float] | None = None
        fail_if_empty = self._fail_on_no_candidate if fail_on_no_candidate is None else fail_on_no_candidate

        chosen_model = model if model is not None else self._model
        chosen_temperature = temperature if temperature is not None else self._temperature
        num_candidates = max(1, candidates if candidates is not None else self._candidates)
        rounds = max(1, max_rounds if max_rounds is not None else self._max_rounds)
        system = system_prompt or self._system_prompt

        for _ in range(rounds):
            try:
                result = await self.client.generate(
                    prompt=prompt,
                    system=system,
                    model=chosen_model,
                    n=num_candidates,
                    temperature=chosen_temperature,
                    extra_messages=extra_messages,
                )
            except Exception:  # noqa: BLE001
                continue

            for diff_text in result.candidates:
                try:
                    validate_model_response(diff_text)
                    hunks = parse_diff(diff_text)
                    new_source = apply_diff(block.content, hunks)
                except ValueError:
                    continue

                updated_program = replace_block(source, block, new_source)
                try:
                    metrics = dict(task.evaluation(updated_program))
                except Exception:  # noqa: BLE001
                    continue
                if metrics:
                    task.program_path.write_text(updated_program)
                    accepted_metrics = metrics
                    break
            if accepted_metrics is not None:
                break

        if accepted_metrics is None:
            if fail_if_empty:
                raise RuntimeError("No candidate diff produced an improved program")
            task.program_path.write_text(source)
            return baseline_metrics

        return accepted_metrics
