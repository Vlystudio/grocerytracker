"""Supabase data-access layer.

The local agent authenticates with the SERVICE ROLE key, so it bypasses Row
Level Security and can read configs + write records. This module is the ONLY
place that talks to Supabase, which keeps the rest of the code testable.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timedelta
from typing import Any, Optional

from supabase import Client, create_client

from .config import settings
from .logging_conf import get_logger
from .models import ResearchRecord, SiteConfig

log = get_logger(__name__)


class Database:
    def __init__(self) -> None:
        settings.validate()
        self.client: Client = create_client(
            settings.supabase_url, settings.supabase_service_key
        )

    # ---- Sources -------------------------------------------------------

    def get_enabled_sources(self) -> list[SiteConfig]:
        """All sources the agent is allowed to crawl."""
        res = (
            self.client.table("research_sources")
            .select("*")
            .eq("enabled", True)
            .execute()
        )
        return [SiteConfig(**row) for row in res.data]

    def get_source(self, source_id: str) -> Optional[SiteConfig]:
        res = (
            self.client.table("research_sources")
            .select("*")
            .eq("id", source_id)
            .limit(1)
            .execute()
        )
        return SiteConfig(**res.data[0]) if res.data else None

    def upsert_source(self, cfg: SiteConfig) -> None:
        """Insert/update a source from YAML seeding. Matches on `name`."""
        payload = {
            "name": cfg.name,
            "base_url": cfg.base_url,
            "allowed_domains": cfg.allowed_domains,
            "search_keywords": cfg.search_keywords,
            "crawl_depth": cfg.crawl_depth,
            "rate_limit": cfg.rate_limit,
            "max_pages": cfg.max_pages,
            "engine": cfg.engine,
            "enabled": cfg.enabled,
            "notes": cfg.notes,
        }
        self.client.table("research_sources").upsert(
            payload, on_conflict="name"
        ).execute()

    # ---- Topics --------------------------------------------------------

    def get_topics(self) -> list[dict[str, Any]]:
        return self.client.table("research_topics").select("*").execute().data

    # ---- Grocery: locations, stores, deals -----------------------------

    def get_enabled_locations(self) -> list[dict[str, Any]]:
        return (
            self.client.table("grocery_locations")
            .select("*")
            .eq("enabled", True)
            .execute()
            .data
        )

    def get_enabled_stores(self) -> list[dict[str, Any]]:
        return (
            self.client.table("grocery_stores")
            .select("*")
            .eq("enabled", True)
            .execute()
            .data
        )

    def load_deal_ids(self) -> set[int]:
        """All existing Flipp item ids, paginated past PostgREST's 1000-row cap."""
        ids: set[int] = set()
        page, start = 1000, 0
        while True:
            rows = (
                self.client.table("grocery_deals")
                .select("flipp_item_id")
                .range(start, start + page - 1)
                .execute()
                .data
            )
            for r in rows:
                if r.get("flipp_item_id") is not None:
                    ids.add(r["flipp_item_id"])
            if len(rows) < page:
                break
            start += page
        return ids

    def insert_deals(self, rows: list[dict[str, Any]]) -> int:
        """Insert deals idempotently. Duplicates (same flipp_item_id) are skipped
        rather than raising, so a re-run can't error on already-stored items.
        Returns the number of rows actually inserted."""
        if not rows:
            return 0
        res = (
            self.client.table("grocery_deals")
            .upsert(rows, on_conflict="flipp_item_id", ignore_duplicates=True)
            .execute()
        )
        return len(res.data or [])

    def delete_expired_deals(self, grace_days: int = 2) -> int:
        """Remove deals whose validity ended more than `grace_days` ago, so the
        table stays clean/accurate automatically. Returns rows removed."""
        cutoff = (datetime.utcnow() - timedelta(days=grace_days)).isoformat()
        res = (
            self.client.table("grocery_deals")
            .delete()
            .lt("valid_to", cutoff)
            .execute()
        )
        return len(res.data or [])

    # ---- Dedup indexes -------------------------------------------------

    def load_dedup_index(self) -> "DedupIndex":
        """Pull lightweight columns to detect duplicates in memory.

        For a local aggregator the record count is modest, so loading
        url/doi/title once per run is cheap and far simpler than per-record
        round trips.
        """
        rows = (
            self.client.table("research_records")
            .select("url, doi, title_normalized")
            .execute()
            .data
        )
        return DedupIndex(rows)

    # ---- Records -------------------------------------------------------

    def insert_record(self, record: ResearchRecord) -> Optional[str]:
        """Insert a record + its tables. Returns the new record id (or None)."""
        res = self.client.table("research_records").insert(record.to_db()).execute()
        if not res.data:
            return None
        record_id = res.data[0]["id"]

        if record.tables:
            rows = []
            for tbl in record.tables:
                row = tbl.to_db()
                row["record_id"] = record_id
                rows.append(row)
            self.client.table("extracted_tables").insert(rows).execute()

        return record_id

    # ---- Runs (also the manual-trigger queue) --------------------------

    def claim_queued_runs(self) -> list[dict[str, Any]]:
        """Find admin-queued manual runs and mark them running (claim them)."""
        queued = (
            self.client.table("scrape_runs")
            .select("*")
            .eq("status", "queued")
            .execute()
            .data
        )
        claimed = []
        for run in queued:
            updated = (
                self.client.table("scrape_runs")
                .update({"status": "running", "started_at": _now()})
                .eq("id", run["id"])
                .eq("status", "queued")  # avoid double-claim races
                .execute()
            )
            if updated.data:
                claimed.append(updated.data[0])
        return claimed

    def start_run(self, source_id: Optional[str], trigger: str) -> str:
        res = (
            self.client.table("scrape_runs")
            .insert(
                {
                    "source_id": source_id,
                    "trigger": trigger,
                    "status": "running",
                    "started_at": _now(),
                }
            )
            .execute()
        )
        return res.data[0]["id"]

    def finish_run(self, run_id: str, status: str, **stats: Any) -> None:
        payload: dict[str, Any] = {"status": status, "finished_at": _now()}
        payload.update(stats)
        self.client.table("scrape_runs").update(payload).eq("id", run_id).execute()

    # ---- Errors --------------------------------------------------------

    def log_error(
        self,
        run_id: Optional[str],
        source_id: Optional[str],
        url: Optional[str],
        error_type: str,
        exc: BaseException | str,
    ) -> None:
        message = str(exc)
        tb = (
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            if isinstance(exc, BaseException)
            else None
        )
        try:
            self.client.table("scrape_errors").insert(
                {
                    "run_id": run_id,
                    "source_id": source_id,
                    "url": url,
                    "error_type": error_type,
                    "message": message[:2000],
                    "traceback": tb,
                }
            ).execute()
        except Exception as e:  # never let error logging crash the crawl
            log.error("Failed to write scrape_error to DB: %s", e)


class DedupIndex:
    """In-memory snapshot of existing records for fast duplicate checks."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.urls: set[str] = {r["url"] for r in rows if r.get("url")}
        self.dois: set[str] = {r["doi"] for r in rows if r.get("doi")}
        self.titles: list[str] = [
            r["title_normalized"] for r in rows if r.get("title_normalized")
        ]

    def add(self, record: ResearchRecord, normalized_title: str) -> None:
        """Keep the index current so duplicates within the same run are caught."""
        self.urls.add(record.url)
        if record.doi:
            self.dois.add(record.doi)
        if normalized_title:
            self.titles.append(normalized_title)


def _now() -> str:
    return datetime.utcnow().isoformat()
