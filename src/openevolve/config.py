"""Configuration helpers for OpenEvolve."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

try:  # pragma: no cover - exercised when optional dependency installed
    from pydantic import Field  # type: ignore
    from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore
except ImportError:  # pragma: no cover - fallback executed in constrained environments

    class Field:  # type: ignore[override]
        def __init__(self, default: Any = None, alias: str | None = None) -> None:
            self.default = default
            self.alias = alias

    class BaseSettings:  # type: ignore[override]
        def __init__(self, **data: Any) -> None:
            annotations = getattr(self.__class__, "__annotations__", {})
            for name, annotation in annotations.items():
                field: Field = getattr(self.__class__, name)  # type: ignore[assignment]
                env_name = field.alias or name.upper()
                env_value = os.getenv(env_name)
                if name in data:
                    value = data[name]
                elif env_value is not None:
                    value = self._convert(env_value, annotation)
                else:
                    value = field.default
                setattr(self, name, value)

        @staticmethod
        def _convert(value: str, annotation: Any) -> Any:
            if annotation in {int, int | None}:  # type: ignore[comparison-overlap]
                try:
                    return int(value)
                except ValueError:
                    return value
            if annotation in {float, float | None}:  # type: ignore[comparison-overlap]
                try:
                    return float(value)
                except ValueError:
                    return value
            if annotation is bool:
                return value.lower() in {"1", "true", "yes"}
            return value

    class SettingsConfigDict:  # type: ignore[override]
        def __init__(self, **_: Any) -> None:
            pass


class OpenEvolveSettings(BaseSettings):
    """Runtime configuration derived from environment variables."""

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    model_primary: str = Field(default="gpt-4.1", alias="OPENEVOLVE_MODEL_PRIMARY")
    model_secondary: str | None = Field(default="gpt-4o-mini", alias="OPENEVOLVE_MODEL_SECONDARY")
    concurrency: int = Field(default=4, alias="OPENEVOLVE_CONCURRENCY")
    pareto_k: int = Field(default=20, alias="OPENEVOLVE_PARETO_K")
    novelty_threshold: float = Field(default=0.15, alias="OPENEVOLVE_NOVELTY_THRESHOLD")
    archive_size: int = Field(default=200, alias="OPENEVOLVE_ARCHIVE_SIZE")

    model_config = SettingsConfigDict(env_prefix="", env_file=None, extra="ignore")

    def openai_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.openai_api_key:
            headers["Authorization"] = f"Bearer {self.openai_api_key}"
        return headers


@lru_cache(maxsize=1)
def load_settings(**overrides: Any) -> OpenEvolveSettings:
    """Load configuration with optional overrides (cached)."""

    return OpenEvolveSettings(**overrides)
