"""Meta prompt evolution primitives."""

from __future__ import annotations

import random

from .db import ProgramDB

DEFAULT_META_PROMPTS = [
    """You are an expert software engineer. Optimise for correctness first, then speed. Provide concise diffs.""",
    """Act as a performance specialist. Prefer aggressive refactors and explain reasoning briefly before the diff.""",
    """Adopt a test-driven mindset. Outline failing tests you expect to pass after the change, then provide the patch.""",
    """Balance exploration and exploitation: propose a bold modification but ensure compatibility with existing tests.""",
]


def seed_meta_prompts(db: ProgramDB) -> list[str]:
    existing = db.list_meta_prompts()
    if existing:
        return [row["meta_prompt_id"] for row in existing]
    ids: list[str] = []
    for template in DEFAULT_META_PROMPTS:
        meta_id = db.insert_meta_prompt(template, parents=[])
        ids.append(meta_id)
    return ids


def select_meta_prompts(db: ProgramDB, n: int) -> list[dict]:
    prompts = db.get_meta_prompts(n)
    if len(prompts) < n:
        # fall back to seeding more prompts by mutation of existing ones
        rng = random.Random()
        while len(prompts) < n:
            base = random.choice(DEFAULT_META_PROMPTS)
            mutated = mutate_meta_prompt(base, rng)
            meta_id = db.insert_meta_prompt(mutated, parents=[])
            prompts.append({"meta_prompt_id": meta_id, "template": mutated, "fitness": 0.0})
    return prompts[:n]


def mutate_meta_prompt(template: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    tweaks = [
        ("increase emphasis on speed", "Focus on micro-optimisations and data-structure tuning."),
        ("encourage exploration", "Include one unconventional idea or alternative approach."),
        ("stress test-first", "List quick checks or tests before writing the patch."),
        ("reduce verbosity", "Keep explanations under three sentences."),
        ("prefer small diffs", "Limit edits to the most relevant EVOLVE blocks and avoid broad refactors."),
    ]
    directive, text = rng.choice(tweaks)
    existing = {line.strip() for line in template.splitlines()}
    if text.strip() in existing:
        return template
    return template.rstrip() + "\n" + text


def evolve_meta_prompts(db: ProgramDB, contributions: dict[str, list[str]]) -> None:
    """Update meta-prompt fitness based on downstream candidate performance."""

    for meta_prompt_id, cand_ids in contributions.items():
        if not cand_ids:
            continue
        evals = db.get_candidate_evals(cand_ids)
        if not evals:
            continue
        # Use simple average of summed metrics as fitness surrogate
        scores: list[float] = []
        for cand_id in cand_ids:
            metrics = evals.get(cand_id)
            if not metrics:
                continue
            scores.append(sum(metrics.values()) / max(len(metrics), 1))
        if not scores:
            continue
        fitness = sum(scores) / len(scores)
        # Normalise to [0, 1] with logistic curve to dampen extremes
        normalised = 1 / (1 + pow(2.71828, -fitness))
        db.update_meta_prompt_fitness(meta_prompt_id, normalised)
