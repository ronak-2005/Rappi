"""LLM settings from backend/llm.env. Only generic fields — no provider names anywhere in code.
Change LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in the file to switch provider or model."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.config.settings import BACKEND_DIR


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_mode: Literal["live", "scripted", "baseline"] = "live"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_s: float = 60.0
    llm_max_retries: int = 2  # SDK retries with short backoff on 429 / 5xx
    llm_min_interval_s: float = 0.0  # pace calls for per-minute limits (e.g. 7 for a 10-requests/min free tier)
    llm_rate_limit_waits: int = 0  # extra long waits (up to 60 s each) on per-minute 429s; per-day limits never wait

    @property
    def label(self) -> str:
        return self.llm_model if self.llm_mode == "live" else self.llm_mode


def load_llm_settings(env_file: str | Path | None = None) -> LLMSettings:
    """Load from `env_file` (relative paths are relative to backend/), default backend/llm.env."""
    path = Path(env_file) if env_file else BACKEND_DIR / "llm.env"
    if not path.is_absolute():
        path = BACKEND_DIR / path
    return LLMSettings(_env_file=path if path.exists() else None)
