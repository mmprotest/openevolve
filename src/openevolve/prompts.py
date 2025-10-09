"""Prompt builders for evolutionary updates."""

from __future__ import annotations

from textwrap import dedent
from typing import Iterable, Mapping

from .diffs import is_valid_diff

PROMPT_FOOTER = dedent(
    """
    Respond with one or more SEARCH/REPLACE patches using exactly this template:
    <<<<<<< SEARCH
    old_code
    =======
    new_code
    >>>>>>> REPLACE
    Do not include any commentary or backticks.
    """
).strip()


def build_prompt(
    *,
    task_description: str,
    block_source: str,
    evaluation_criteria: Mapping[str, float] | None = None,
    reference_summaries: Iterable[str] | None = None,
) -> str:
    """Assemble the user prompt for the model."""

    sections: list[str] = ["Task Description:", task_description.strip(), ""]
    sections.extend(["Target Block:", block_source.strip(), ""])

    if reference_summaries:
        sections.append("Reference Candidates:")
        for summary in reference_summaries:
            sections.append(f"- {summary.strip()}")
        sections.append("")

    if evaluation_criteria:
        sections.append("Evaluation Criteria (higher is better unless noted):")
        for key, value in evaluation_criteria.items():
            sections.append(f"- {key}: {value}")
        sections.append("")

    sections.append(PROMPT_FOOTER)
    return "\n".join(sections).strip()


def validate_model_response(response: str) -> None:
    """Raise if the response is not a valid SEARCH/REPLACE diff."""

    if not is_valid_diff(response):
        raise ValueError("Model response is not a valid SEARCH/REPLACE diff")
