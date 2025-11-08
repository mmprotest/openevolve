"""High level orchestration loop (simplified)."""

from __future__ import annotations

import logging
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
    scoring: Callable[[Mapping[str, float]], float] | None = None


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
        stop_on_first: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = load_settings()
        self.client: LLMClientProtocol = client or build_default_client()
        # Fall back to the configured primary model when no explicit override is provided.
        self._model = model or self.settings.model_primary
        self._temperature = temperature
        self._candidates = max(1, candidates)
        self._max_rounds = max(1, max_rounds)
        self._system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self._fail_on_no_candidate = fail_on_no_candidate
        self._stop_on_first = stop_on_first
        self._logger = logger or logging.getLogger(__name__)

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
        stop_on_first: bool | None = None,
    ) -> Mapping[str, float]:
        source = task.program_path.read_text()
        blocks = extract_blocks(source)
        if not blocks:
            raise RuntimeError("No EVOLVE blocks found in program")
        block = blocks[0]

        baseline_metrics = dict(task.evaluation(source))
        fail_if_empty = self._fail_on_no_candidate if fail_on_no_candidate is None else fail_on_no_candidate
        stop_immediately = self._stop_on_first if stop_on_first is None else stop_on_first

        chosen_model = model if model is not None else self._model
        chosen_temperature = temperature if temperature is not None else self._temperature
        num_candidates = max(1, candidates if candidates is not None else self._candidates)
        rounds = max(1, max_rounds if max_rounds is not None else self._max_rounds)
        system = system_prompt or self._system_prompt

        if task.scoring is not None:
            baseline_score = task.scoring(baseline_metrics)
        else:
            baseline_score = 0.0
        best_score = baseline_score
        best_metrics: Mapping[str, float] = baseline_metrics
        best_program = source
        score_counter = baseline_score

        current_source = source
        current_block = block

        self._logger.info(
            "Starting evolution for %s (rounds=%s, candidates=%s, stop_on_first=%s)",
            task.name,
            rounds,
            num_candidates,
            stop_immediately,
        )

        for round_index in range(rounds):
            self._logger.info(
                "Round %s/%s: requesting %s candidate diff(s)",
                round_index + 1,
                rounds,
                num_candidates,
            )
            prompt = build_prompt(
                task_description=task.description,
                block_source=current_block.content,
            )
            try:
                request_model = chosen_model or self._model
                self._logger.debug(
                    "Invoking language model (model=%s, temperature=%.2f, n=%s)",
                    request_model,
                    chosen_temperature,
                    num_candidates,
                )
                result = await self.client.generate(
                    prompt=prompt,
                    system=system,
                    model=request_model,
                    n=num_candidates,
                    temperature=chosen_temperature,
                    extra_messages=extra_messages,
                )
                self._logger.debug(
                    "Received %s candidate(s) from language model", len(result.candidates)
                )
            except Exception:  # noqa: BLE001
                self._logger.exception("Language model request failed; aborting evolution round")
                continue

            prompt_source = current_source
            prompt_block = current_block

            for candidate_index, diff_text in enumerate(result.candidates, start=1):
                try:
                    validate_model_response(diff_text)
                    hunks = parse_diff(diff_text)
                    new_source = apply_diff(prompt_block.content, hunks)
                except ValueError:
                    self._logger.warning(
                        "Candidate %s in round %s discarded: invalid diff",  # noqa: G004
                        candidate_index,
                        round_index + 1,
                    )
                    continue

                updated_program = replace_block(prompt_source, prompt_block, new_source)
                try:
                    metrics = dict(task.evaluation(updated_program))
                except Exception:  # noqa: BLE001
                    self._logger.exception(
                        "Candidate %s in round %s failed during evaluation",  # noqa: G004
                        candidate_index,
                        round_index + 1,
                    )
                    continue
                if not metrics:
                    self._logger.warning(
                        "Candidate %s in round %s produced no metrics",  # noqa: G004
                        candidate_index,
                        round_index + 1,
                    )
                    continue

                if stop_immediately:
                    self._logger.info(
                        "Accepting first viable candidate %s in round %s",  # noqa: G004
                        candidate_index,
                        round_index + 1,
                    )
                    task.program_path.write_text(updated_program)
                    return metrics

                if task.scoring is not None:
                    candidate_score = task.scoring(metrics)
                else:
                    score_counter += 1.0
                    candidate_score = score_counter

                self._logger.info(
                    "Candidate %s in round %s scored %.4f (best=%.4f)",  # noqa: G004
                    candidate_index,
                    round_index + 1,
                    candidate_score,
                    best_score,
                )

                if candidate_score > best_score:
                    best_score = candidate_score
                    best_metrics = metrics
                    best_program = updated_program
                    self._logger.info(
                        "New best candidate selected from round %s (score=%.4f)",  # noqa: G004
                        round_index + 1,
                        candidate_score,
                    )

            current_source = best_program
            blocks = extract_blocks(current_source)
            if not blocks:
                raise RuntimeError("No EVOLVE blocks found in updated program")
            current_block = blocks[0]

        if best_score == baseline_score:
            if fail_if_empty:
                raise RuntimeError("No candidate diff produced an improved program")
            self._logger.info("Evolution finished without improving on the baseline")
            task.program_path.write_text(source)
            return baseline_metrics

        self._logger.info("Evolution completed with improved program")
        task.program_path.write_text(best_program)
        return best_metrics
