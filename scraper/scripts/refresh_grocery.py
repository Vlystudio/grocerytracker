"""Slim grocery-refresh entrypoint — used by the cloud cron (GitHub Actions).

It imports ONLY the grocery collectors (Flipp + Whole Foods), which depend on
nothing heavy (no Scrapy/Playwright/lxml/BeautifulSoup), so the cloud job
installs a tiny, fast, reliable dependency set (requirements-collect.txt).

Reads Supabase creds from the environment (set as GitHub Actions secrets/env).
Runs fine locally too:  python scripts/refresh_grocery.py
"""
from __future__ import annotations

import pathlib
import sys

# Make the `agent` package importable when run as a plain script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from agent.collectors import run_grocery  # noqa: E402
from agent.db import Database  # noqa: E402


def main() -> None:
    stats = run_grocery(Database(), trigger="scheduled")
    print(
        f"Done. new={stats['new']} found={stats['found']} "
        f"sources={stats['flyers']} errors={stats['errors']}"
    )


if __name__ == "__main__":
    main()
