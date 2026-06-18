"""Standalone Scrapy spider for static pages.

This file is intentionally self-contained so it can be launched in its own
process with `scrapy runspider`. Running Scrapy in a subprocess (instead of
in-process) sidesteps the "reactor is not restartable" problem when crawling
several sources in one agent run, and isolates each crawl.

It is invoked by static_scraper.py, e.g.:

    scrapy runspider scrapy_spider.py \
        -a start_url=https://site/...  \
        -a allowed_domains=site.org    \
        -s DEPTH_LIMIT=1               \
        -s DOWNLOAD_DELAY=2            \
        -s CLOSESPIDER_PAGECOUNT=30    \
        -O out.json

It emits one JSON object per fetched page: {"url", "html", "depth"}.
"""
from __future__ import annotations

import scrapy


class ResearchSpider(scrapy.Spider):
    name = "research"

    # Politeness / robustness defaults. Most are also overridable via -s flags.
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 522, 524, 408],
        "DOWNLOAD_TIMEOUT": 30,
        "HTTPERROR_ALLOW_ALL": False,
        "LOG_LEVEL": "ERROR",
    }

    def __init__(
        self,
        start_url: str = "",
        allowed_domains: str = "",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url else []
        # allowed_domains arrives as a comma-separated string from the CLI.
        self.allowed_domains = [
            d.strip() for d in allowed_domains.split(",") if d.strip()
        ]

    def parse(self, response):
        # Only parse HTML responses (skip PDFs, images, etc.).
        content_type = response.headers.get("Content-Type", b"").decode("latin-1")
        if "html" not in content_type.lower():
            return

        yield {
            "url": response.url,
            "html": response.text,
            "depth": response.meta.get("depth", 0),
        }

        # Follow same-site links. Scrapy's DEPTH_LIMIT (set via -s) stops the
        # crawl from going deeper than configured, so we don't track depth here.
        for href in response.css("a::attr(href)").getall():
            if href and not href.startswith(("mailto:", "javascript:", "#")):
                yield response.follow(href, callback=self.parse)
