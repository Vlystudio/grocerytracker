"""Local scheduler.

Two responsibilities while running as a long-lived process:
  1. Kick off a full crawl once a day at DAILY_RUN_TIME.
  2. Poll Supabase for admin-queued manual runs and execute them.

This is how the website triggers a scan WITHOUT scraping itself: the admin page
inserts a `scrape_runs` row with status='queued'; this loop claims and runs it.
"""
from __future__ import annotations

import time

import schedule

from .ai.extractor import AIExtractor
from .collectors.flipp import collect as collect_grocery
from .config import settings
from .db import Database
from .logging_conf import get_logger
from .pipeline import execute_run

log = get_logger(__name__)

# Admin-queued runs whose notes start with this marker are grocery jobs.
GROCERY_MARKER = "grocery"


def _daily_job(db: Database, ai: AIExtractor) -> None:
    log.info("Scheduled daily run starting…")
    # 1) Grocery deals (the primary job).
    try:
        collect_grocery(db, trigger="scheduled")
    except Exception as e:  # noqa: BLE001 — keep the scheduler alive
        log.exception("Daily grocery collect crashed: %s", e)
    # 2) Research crawl, only if any research sources are still enabled.
    try:
        if db.get_enabled_sources():
            run_id = db.start_run(source_id=None, trigger="scheduled")
            execute_run(db, run_id, source_id=None, ai=ai)
    except Exception as e:  # noqa: BLE001
        log.exception("Daily research crawl crashed: %s", e)


def _drain_queue(db: Database, ai: AIExtractor) -> None:
    """Run any manual jobs the admin queued from the dashboard."""
    try:
        claimed = db.claim_queued_runs()
    except Exception as e:  # noqa: BLE001
        log.error("Could not poll run queue: %s", e)
        return

    for run in claimed:
        is_grocery = (run.get("notes") or "").startswith(GROCERY_MARKER)
        kind = "grocery" if is_grocery else "research"
        log.info("Executing queued %s run %s", kind, run["id"][:8])
        try:
            if is_grocery:
                collect_grocery(db, run_id=run["id"])
            else:
                execute_run(db, run["id"], run.get("source_id"), ai=ai)
        except Exception as e:  # noqa: BLE001
            log.exception("Queued run %s failed: %s", run["id"][:8], e)
            db.finish_run(run["id"], "failed", notes=str(e)[:500])


def start_scheduler() -> None:
    settings.validate()
    db = Database()
    ai = AIExtractor()

    schedule.every().day.at(settings.daily_run_time).do(_daily_job, db=db, ai=ai)
    log.info(
        "Scheduler running. Daily crawl at %s; polling queue every %ss. Ctrl+C to stop.",
        settings.daily_run_time,
        settings.queue_poll_seconds,
    )

    # Check the manual-run queue immediately on startup, then on each tick.
    _drain_queue(db, ai)
    try:
        while True:
            schedule.run_pending()
            _drain_queue(db, ai)
            time.sleep(settings.queue_poll_seconds)
    except KeyboardInterrupt:
        log.info("Scheduler stopped.")
