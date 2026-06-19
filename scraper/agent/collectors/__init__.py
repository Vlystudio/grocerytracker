"""Data collectors for grocery deals.

Unlike the research scrapers (which crawl HTML), collectors pull from
structured endpoints:
  * flipp.py      — weekly flyers for most chains (Hannaford, Shaw's, ...)
  * wholefoods.py — Whole Foods sales (its own JSON API)

`run_grocery()` runs both under a single scrape_runs row and aggregates stats.
"""
from __future__ import annotations

from typing import Optional

from ..db import Database
from ..logging_conf import get_logger

log = get_logger(__name__)


def run_grocery(
    db: Database, trigger: str = "manual", run_id: Optional[str] = None
) -> dict[str, int]:
    """Run all grocery collectors (Flipp + Whole Foods) under one run.

    If `run_id` is given (e.g. an admin-queued run already claimed by the
    scheduler), that row is updated; otherwise a new run is created.
    """
    from . import flipp, wholefoods

    run_id = run_id or db.start_run(source_id=None, trigger=trigger)

    total = {"flyers": 0, "found": 0, "new": 0, "errors": 0}
    for name, fn in (("flipp", flipp.collect_into), ("wholefoods", wholefoods.collect_into)):
        try:
            stats = fn(db, run_id)
        except Exception as e:  # noqa: BLE001 — one collector failing shouldn't stop the other
            log.exception("%s collector crashed: %s", name, e)
            db.log_error(run_id, None, name, "collector", e)
            stats = {"flyers": 0, "found": 0, "new": 0, "errors": 1}
        for k in total:
            total[k] += stats.get(k, 0)

    status = (
        "failed"
        if (total["new"] == 0 and total["errors"] > 0)
        else ("partial" if total["errors"] else "success")
    )
    db.finish_run(
        run_id,
        status,
        pages_crawled=total["flyers"],
        records_found=total["found"],
        records_new=total["new"],
        errors_count=total["errors"],
    )
    log.info(
        "Grocery run done: %d sources, %d deals found, %d new, %d errors (%s)",
        total["flyers"],
        total["found"],
        total["new"],
        total["errors"],
        status,
    )
    return total
