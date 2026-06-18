"""The orchestration layer that ties everything together.

For each source:  crawl -> parse -> keyword filter -> AI extract -> validate
                  -> dedup -> store, while recording stats and errors.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .ai.extractor import AIExtractor
from .config import settings
from .db import Database, DedupIndex
from .dedup import find_duplicate_reason
from .logging_conf import get_logger
from .models import ResearchRecord, SiteConfig, normalize_title
from .scrapers.dynamic_scraper import crawl_dynamic
from .scrapers.parse import matches_keywords, parse_page
from .scrapers.static_scraper import crawl_static

log = get_logger(__name__)


@dataclass
class RunStats:
    pages_crawled: int = 0
    records_found: int = 0
    records_new: int = 0
    errors_count: int = 0

    def merge(self, other: "RunStats") -> None:
        self.pages_crawled += other.pages_crawled
        self.records_found += other.records_found
        self.records_new += other.records_new
        self.errors_count += other.errors_count


def _crawl_with_retry(cfg: SiteConfig):
    """Run the appropriate engine, retrying the whole crawl on transient errors."""
    engine = crawl_dynamic if cfg.engine == "playwright" else crawl_static
    last_exc: Optional[Exception] = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            return engine(cfg)
        except Exception as e:  # noqa: BLE001 — we want to retry anything transient
            last_exc = e
            wait = min(2 ** attempt, 30)
            log.warning(
                "Crawl attempt %d/%d failed for %s: %s (retrying in %ss)",
                attempt,
                settings.max_retries,
                cfg.name,
                e,
                wait,
            )
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def process_source(
    db: Database,
    cfg: SiteConfig,
    ai: AIExtractor,
    run_id: str,
    index: DedupIndex,
) -> RunStats:
    """Crawl and ingest a single source. Errors are logged, never fatal."""
    stats = RunStats()
    log.info("=== Source: %s (%s) ===", cfg.name, cfg.engine)

    # --- Crawl (with retry). A hard failure here ends this source only. ---
    try:
        pages = _crawl_with_retry(cfg)
    except Exception as e:  # noqa: BLE001
        db.log_error(run_id, cfg.id, cfg.base_url, "crawl", e)
        stats.errors_count += 1
        return stats

    stats.pages_crawled = len(pages)

    for page in pages:
        try:
            parsed = parse_page(page.html, page.url)

            # Keep only real article pages that match the source's keywords.
            if not parsed.looks_like_article():
                continue
            if not matches_keywords(parsed, cfg.search_keywords):
                continue

            stats.records_found += 1

            # --- AI enrichment (fills the fuzzy fields; degrades gracefully) ---
            ai_out = ai.extract(
                title=parsed.title,
                existing_abstract=parsed.abstract,
                keywords=cfg.search_keywords,
                body_text=parsed.main_text,
            )

            record = ResearchRecord(
                title=parsed.title or "(untitled)",
                url=page.url,
                doi=parsed.doi,
                authors=parsed.authors,
                publication_date=parsed.publication_date,
                abstract=ai_out.abstract or parsed.abstract,
                summary=ai_out.summary,
                study_type=ai_out.study_type,
                sample_size=ai_out.sample_size,
                key_findings=ai_out.key_findings,
                pdf_links=parsed.pdf_links,
                tables=parsed.tables,
                source_id=cfg.id,
                source_website=_host(page.url),
                raw_text=parsed.main_text,
                extraction_engine=ai_out.engine,
            )

            # --- Dedup: URL -> DOI -> fuzzy title ---
            reason = find_duplicate_reason(record, index)
            if reason:
                log.info("Skipping duplicate (%s): %s", reason, record.title[:70])
                continue

            new_id = db.insert_record(record)
            if new_id:
                index.add(record, normalize_title(record.title))
                stats.records_new += 1
                log.info("Stored: %s", record.title[:80])

        except Exception as e:  # noqa: BLE001 — one bad page shouldn't stop the rest
            db.log_error(run_id, cfg.id, page.url, "parse", e)
            stats.errors_count += 1

    log.info(
        "Source done: %d pages, %d candidates, %d new, %d errors",
        stats.pages_crawled,
        stats.records_found,
        stats.records_new,
        stats.errors_count,
    )
    return stats


def execute_run(
    db: Database,
    run_id: str,
    source_id: Optional[str],
    ai: Optional[AIExtractor] = None,
) -> RunStats:
    """Execute an already-created run row against one or all enabled sources."""
    ai = ai or AIExtractor()
    index = db.load_dedup_index()

    if source_id:
        src = db.get_source(source_id)
        sources = [src] if src else []
    else:
        sources = db.get_enabled_sources()

    total = RunStats()
    for cfg in sources:
        total.merge(process_source(db, cfg, ai, run_id, index))

    status = _derive_status(total)
    db.finish_run(
        run_id,
        status,
        pages_crawled=total.pages_crawled,
        records_found=total.records_found,
        records_new=total.records_new,
        errors_count=total.errors_count,
    )
    log.info(
        "Run %s finished: status=%s, new=%d, errors=%d",
        run_id[:8],
        status,
        total.records_new,
        total.errors_count,
    )
    return total


def run_all(db: Database, trigger: str = "manual") -> RunStats:
    """Create a run row covering all enabled sources, then execute it."""
    run_id = db.start_run(source_id=None, trigger=trigger)
    return execute_run(db, run_id, source_id=None)


def _derive_status(stats: RunStats) -> str:
    if stats.records_new == 0 and stats.errors_count > 0 and stats.records_found == 0:
        return "failed"
    if stats.errors_count > 0:
        return "partial"
    return "success"


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.lower()
