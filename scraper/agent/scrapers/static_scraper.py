"""Static crawler: drives the Scrapy spider in a subprocess and collects pages.

We shell out to `scrapy runspider` and read its JSON feed back in. This keeps
each crawl isolated and avoids Twisted reactor reuse issues across sources.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from ..config import settings
from ..logging_conf import get_logger
from ..models import SiteConfig
from . import FetchedPage

log = get_logger(__name__)

_SPIDER_PATH = Path(__file__).resolve().parent / "scrapy_spider.py"


def crawl_static(cfg: SiteConfig) -> list[FetchedPage]:
    """Run the Scrapy spider for one source and return fetched pages."""
    out_file = Path(tempfile.gettempdir()) / f"scrapy_{abs(hash(cfg.base_url))}.json"
    if out_file.exists():
        out_file.unlink()

    cmd = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(_SPIDER_PATH),
        "-a",
        f"start_url={cfg.base_url}",
        "-a",
        f"allowed_domains={','.join(cfg.allowed_domains)}",
        "-s",
        f"DEPTH_LIMIT={cfg.crawl_depth}",
        "-s",
        f"DOWNLOAD_DELAY={cfg.rate_limit}",
        "-s",
        f"CLOSESPIDER_PAGECOUNT={cfg.max_pages}",
        "-s",
        f"DOWNLOAD_TIMEOUT={settings.http_timeout}",
        "-s",
        f"RETRY_TIMES={settings.max_retries}",
        "-s",
        f"USER_AGENT={settings.user_agent}",
        "-O",
        f"{out_file}",
    ]

    log.info("Scrapy crawl: %s (depth=%s, max_pages=%s)", cfg.name, cfg.crawl_depth, cfg.max_pages)
    try:
        # Generous timeout; the spider self-limits via CLOSESPIDER_PAGECOUNT.
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.http_timeout * cfg.max_pages + 120,
        )
    except subprocess.CalledProcessError as e:
        log.error("Scrapy failed for %s: %s", cfg.name, e.stderr[-1000:] if e.stderr else e)
        raise
    except subprocess.TimeoutExpired:
        log.warning("Scrapy timed out for %s; using whatever was collected", cfg.name)

    if not out_file.exists():
        return []

    try:
        rows = json.loads(out_file.read_text(encoding="utf-8") or "[]")
    finally:
        out_file.unlink(missing_ok=True)

    pages = [
        FetchedPage(url=r["url"], html=r.get("html", ""), depth=r.get("depth", 0))
        for r in rows
        if r.get("html")
    ]
    log.info("Scrapy fetched %d page(s) from %s", len(pages), cfg.name)
    return pages
