"""Central configuration loaded from environment variables (.env).

Everything tunable lives here so the rest of the codebase can import a single
`settings` object instead of reading os.environ all over the place.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env that sits next to the `scraper/` folder (one level up from agent/).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _get_float(name: str, default: float) -> float:
    try:
        return float(_get(name) or default)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # ---- Supabase ----
    supabase_url: str = field(default_factory=lambda: _get("SUPABASE_URL"))
    supabase_service_key: str = field(
        default_factory=lambda: _get("SUPABASE_SERVICE_ROLE_KEY")
    )

    # ---- AI provider selection ----
    ai_provider: str = field(default_factory=lambda: _get("AI_PROVIDER", "auto").lower())
    ollama_base_url: str = field(
        default_factory=lambda: _get("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(default_factory=lambda: _get("OLLAMA_MODEL", "llama3.1"))
    openai_api_key: str = field(default_factory=lambda: _get("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _get("OPENAI_MODEL", "gpt-4o-mini"))
    anthropic_api_key: str = field(default_factory=lambda: _get("ANTHROPIC_API_KEY"))
    anthropic_model: str = field(
        default_factory=lambda: _get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    )

    # ---- Scheduler ----
    daily_run_time: str = field(default_factory=lambda: _get("DAILY_RUN_TIME", "03:00"))
    queue_poll_seconds: int = field(
        default_factory=lambda: _get_int("QUEUE_POLL_SECONDS", 30)
    )

    # ---- Crawler defaults ----
    default_rate_limit: float = field(
        default_factory=lambda: _get_float("DEFAULT_RATE_LIMIT", 2.0)
    )
    http_timeout: int = field(default_factory=lambda: _get_int("HTTP_TIMEOUT", 30))
    max_retries: int = field(default_factory=lambda: _get_int("MAX_RETRIES", 3))
    user_agent: str = field(
        default_factory=lambda: _get("USER_AGENT", "ResearchAgent/1.0")
    )

    # ---- Dedup ----
    fuzzy_title_threshold: int = field(
        default_factory=lambda: _get_int("FUZZY_TITLE_THRESHOLD", 90)
    )

    # ---- Logging ----
    log_level: str = field(default_factory=lambda: _get("LOG_LEVEL", "INFO").upper())
    log_dir: str = field(default_factory=lambda: _get("LOG_DIR", "logs"))

    def validate(self) -> None:
        """Fail fast with a clear message if required config is missing."""
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if missing:
            raise SystemExit(
                "Missing required environment variables: "
                + ", ".join(missing)
                + f"\nCreate {_ENV_PATH} from .env.example and fill them in."
            )


settings = Settings()
