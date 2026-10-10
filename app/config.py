"""Runtime configuration. Every secret comes from environment variables, never from code."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    llm_timeout_s: int
    max_llm_calls_per_day: int
    max_image_bytes: int
    rate_analyze_per_min: int
    rate_other_per_min: int
    enable_explanation: bool


def load_settings() -> Settings:
    key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip() or None
    return Settings(
        api_key=key,
        model=os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash"),
        llm_timeout_s=_int("LLM_TIMEOUT_S", 40),
        max_llm_calls_per_day=_int("MAX_LLM_CALLS_PER_DAY", 300),
        max_image_bytes=_int("MAX_IMAGE_MB", 5) * 1024 * 1024,
        rate_analyze_per_min=_int("RATE_ANALYZE_PER_MIN", 6),
        rate_other_per_min=_int("RATE_OTHER_PER_MIN", 40),
        enable_explanation=_bool("ENABLE_EXPLANATION", True),
    )
