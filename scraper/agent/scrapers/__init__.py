"""Scraping engines: static (Scrapy) and dynamic (Playwright).

Both engines return a list of `FetchedPage` objects so the rest of the
pipeline (parsing, AI extraction, storage) is engine-agnostic.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FetchedPage:
    """Raw output of a crawl: a URL and the HTML we retrieved for it."""

    url: str
    html: str
    depth: int = 0
    status: int = 200
