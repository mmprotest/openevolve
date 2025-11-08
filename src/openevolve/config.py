"""Configuration helpers for legacy settings and new YAML configs."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULTS: dict[str, Any] = {
    "db_path": ".openevolve/openevolve.db",
    "artifacts_root": "runs",
    "population_size": 8,
    "generations": 5,
    "selection": {"elite": 4, "novel": 2, "young": 2},
    "metrics": {},
    "sampler": {"budget_tokens": 4000, "elites_k": 4, "novel_m": 4, "include_failures": 2},
    "cascade": {"max_parallel": 4, "cancel_on_fail": False, "evaluators": []},
    "meta_prompt": {"population": 4, "mutation_prob": 0.2, "selection_top_k": 3},
    "archive": {"capacity": 200, "k_novelty": 8, "ageing_threshold": 6},
    "evolution": {"scope": "blocks", "apply_safe_revert": True},
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = copy.deepcopy(DEFAULTS)
    if path:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load configuration files")
        with Path(path).open("r", encoding="utf-8") as fh:
            file_cfg = yaml.safe_load(fh) or {}
        config = _merge_dict(config, file_cfg)
    if overrides:
        config = _merge_dict(config, overrides)
    return config


class OpenEvolveSettings(BaseSettings):
    """Environment driven settings for the original controller pipeline."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    model_primary: str = Field(default="gpt-4.1", alias="OPENEVOLVE_MODEL_PRIMARY")
    model_secondary: str | None = Field(default="gpt-4o-mini", alias="OPENEVOLVE_MODEL_SECONDARY")
    concurrency: int = Field(default=4, alias="OPENEVOLVE_CONCURRENCY")
    pareto_k: int = Field(default=20, alias="OPENEVOLVE_PARETO_K")
    novelty_threshold: float = Field(default=0.15, alias="OPENEVOLVE_NOVELTY_THRESHOLD")
    archive_size: int = Field(default=200, alias="OPENEVOLVE_ARCHIVE_SIZE")


def load_settings() -> OpenEvolveSettings:
    """Return settings initialised from environment."""

    return OpenEvolveSettings()
