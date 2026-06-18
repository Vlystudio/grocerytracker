"""Dynamic crawler for JavaScript-rendered pages, using Playwright.

A simple breadth-first crawl: render a page, capture its HTML after the network
settles, then enqueue same-domain links until we hit the depth or page cap.

Requires a one-time browser install:  playwright install chromium
"""
from __future__ import annotations

import time
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

from ..config import settings
from ..logging_conf import get_logger
from ..models import SiteConfig
from . import FetchedPage

log = get_logger(__name__)


def _same_site(url: str, allowed_domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in allowed_domains)


def crawl_dynamic(cfg: SiteConfig) -> list[FetchedPage]:
    # Imported lazily so the agent still runs (for static sources) even if
    # Playwright browsers aren't installed yet.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Playwright is not installed. Run `pip install playwright` and "
            "`playwright install chromium`."
        ) from e

    pages: list[FetchedPage] = []
    seen: set[str] = set()
    # Queue of (url, depth).
    queue: deque[tuple[str, int]] = deque([(cfg.base_url, 0)])

    log.info(
        "Playwright crawl: %s (depth=%s, max_pages=%s)",
        cfg.name,
        cfg.crawl_depth,
        cfg.max_pages,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=settings.user_agent,
            ignore_https_errors=True,
        )
        page = context.new_page()

        while queue and len(pages) < cfg.max_pages:
            url, depth = queue.popleft()
            url, _ = urldefrag(url)
            if url in seen:
                continue
            seen.add(url)

            try:
                page.goto(url, wait_until="networkidle", timeout=settings.http_timeout * 1000)
                html = page.content()
                pages.append(FetchedPage(url=url, html=html, depth=depth))
            except Exception as e:
                log.warning("Playwright failed on %s: %s", url, e)
                # Re-raise only nothing — record-level errors are logged by the
                # pipeline; here we just skip the page.
                continue

            # Enqueue child links if we can go deeper.
            if depth < cfg.crawl_depth:
                try:
                    hrefs = page.eval_on_selector_all(
                        "a[href]", "els => els.map(e => e.href)"
                    )
                except Exception:
                    hrefs = []
                for href in hrefs:
                    nxt = urljoin(url, href)
                    if nxt not in seen and _same_site(nxt, cfg.allowed_domains):
                        queue.append((nxt, depth + 1))

            time.sleep(cfg.rate_limit)  # politeness / rate limiting

        context.close()
        browser.close()

    log.info("Playwright fetched %d page(s) from %s", len(pages), cfg.name)
    return pages
