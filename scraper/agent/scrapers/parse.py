"""HTML -> structured fields, using BeautifulSoup + lxml.

Strategy: pull the high-confidence bibliographic fields straight from standard
metadata (Highwire/Dublin Core `citation_*` and OpenGraph tags), grab tables
and PDF links structurally, and produce a cleaned plain-text body that the AI
layer can mine for the fuzzier fields (study type, sample size, key findings).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..models import ExtractedTable

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")


@dataclass
class ParsedPage:
    url: str
    title: str | None = None
    doi: str | None = None
    doi_from_meta: bool = False   # True only when DOI came from the page's own meta
    authors: list[str] = field(default_factory=list)
    publication_date: str | None = None
    abstract: str | None = None
    pdf_links: list[str] = field(default_factory=list)
    tables: list[ExtractedTable] = field(default_factory=list)
    main_text: str = ""

    def looks_like_article(self) -> bool:
        """Heuristic: a real paper page declares its OWN DOI in metadata.

        We require a DOI that came from the page's `citation_doi`/`dc.identifier`
        meta (not one merely scanned out of the HTML), which avoids capturing
        journal landing/nav pages that link to featured articles. If you target
        sources whose articles lack DOI meta, relax this to
        `self.title and (self.doi or self.abstract)`.
        """
        return bool(self.title and self.doi_from_meta)


def _meta(soup: BeautifulSoup, *names: str) -> list[str]:
    """Return all meta tag contents matching any of the given name/property."""
    out: list[str] = []
    for name in names:
        for tag in soup.find_all("meta", attrs={"name": name}):
            if tag.get("content"):
                out.append(tag["content"].strip())
        for tag in soup.find_all("meta", attrs={"property": name}):
            if tag.get("content"):
                out.append(tag["content"].strip())
    return out


def _first(values: list[str]) -> str | None:
    return values[0] if values else None


def parse_page(html: str, url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    page = ParsedPage(url=url)

    # ---- Title ----
    page.title = (
        _first(_meta(soup, "citation_title", "dc.title", "og:title"))
        or (soup.title.string.strip() if soup.title and soup.title.string else None)
        or (soup.h1.get_text(strip=True) if soup.h1 else None)
    )

    # ---- DOI ----
    # Authoritative: the page's own citation metadata.
    page.doi = _first(_meta(soup, "citation_doi", "dc.identifier"))
    page.doi_from_meta = bool(page.doi)
    if not page.doi:
        # Fallback for storage only (NOT used to decide if this is an article),
        # since a loose scan can match DOIs from links/citations on the page.
        m = _DOI_RE.search(html)
        page.doi = m.group(0) if m else None

    # ---- Authors ----
    authors = _meta(soup, "citation_author", "dc.creator", "author")
    # Some sites put all authors in one comma-separated meta tag.
    if len(authors) == 1 and "," in authors[0]:
        authors = [a.strip() for a in authors[0].split(",") if a.strip()]
    page.authors = authors

    # ---- Publication date ----
    page.publication_date = _first(
        _meta(
            soup,
            "citation_publication_date",
            "citation_date",
            "dc.date",
            "article:published_time",
        )
    )

    # ---- Abstract ----
    page.abstract = _first(_meta(soup, "citation_abstract", "dc.description"))
    if not page.abstract:
        node = soup.find(attrs={"class": re.compile(r"abstract", re.I)}) or soup.find(
            id=re.compile(r"abstract", re.I)
        )
        if node:
            page.abstract = node.get_text(" ", strip=True)
    if not page.abstract:
        page.abstract = _first(_meta(soup, "og:description", "description"))

    # ---- PDF links ----
    pdfs = set(_meta(soup, "citation_pdf_url"))
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf") or "/pdf" in href.lower():
            pdfs.add(urljoin(url, href))
    page.pdf_links = sorted(pdfs)

    # ---- Tables ----
    page.tables = _extract_tables(soup)

    # ---- Cleaned main text for the AI layer ----
    page.main_text = _clean_text(soup)

    return page


def _extract_tables(soup: BeautifulSoup) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []
    for i, table in enumerate(soup.find_all("table")):
        headers: list[str] = [
            th.get_text(" ", strip=True) for th in table.find_all("th")
        ]
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if cells:
                rows.append([td.get_text(" ", strip=True) for td in cells])

        if not headers and not rows:
            continue

        caption_el = table.find("caption")
        caption = caption_el.get_text(" ", strip=True) if caption_el else None
        tables.append(
            ExtractedTable(
                table_index=i, caption=caption, headers=headers, rows=rows[:200]
            )
        )
    return tables


def _clean_text(soup: BeautifulSoup) -> str:
    """Strip boilerplate and return readable body text (capped)."""
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "form"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    # Collapse runs of blank lines.
    text = re.sub(r"\n{2,}", "\n", text)
    return text[:15000]  # plenty for extraction; keeps AI prompts small


def matches_keywords(page: ParsedPage, keywords: list[str]) -> bool:
    """True if no keywords given, or any keyword appears in title/abstract/text."""
    if not keywords:
        return True
    haystack = " ".join(
        filter(None, [page.title, page.abstract, page.main_text[:4000]])
    ).lower()
    return any(kw.lower() in haystack for kw in keywords)
