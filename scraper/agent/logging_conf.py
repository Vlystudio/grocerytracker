"""Logging setup: pretty console output (rich) + a rotating file log.

Import `get_logger(__name__)` anywhere to log consistently.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from .config import settings

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, settings.log_level, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler — colorful and concise.
    console = RichHandler(rich_tracebacks=True, show_path=False)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(message)s", datefmt="%H:%M:%S"))

    # File handler — full detail, rotated at ~2 MB, keeping 5 backups.
    file_handler = RotatingFileHandler(
        log_dir / "agent.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root.handlers.clear()
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("scrapy").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
