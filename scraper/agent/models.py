"""Typed data models.

`SiteConfig`   — a crawl target (mirrors a research_sources row).
`ExtractedTable` — one table found on a page.
`ResearchRecord` — the final, validated record we store in Supabase.

Pydantic gives us free validation/coercion of the messy JSON the AI returns.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SiteConfig(BaseModel):
    """One crawl target. Loaded from Supabase or sites.yaml."""

    id: Optional[str] = None
    name: str
    base_url: str
    allowed_domains: list[str] = Field(default_factory=list)
    search_keywords: list[str] = Field(default_factory=list)
    crawl_depth: int = 1
    rate_limit: float = 2.0
    max_pages: int = 50
    engine: str = "scrapy"  # "scrapy" | "playwright"
    enabled: bool = True
    notes: Optional[str] = None


class ExtractedTable(BaseModel):
    """A single HTML table normalized to headers + rows."""

    table_index: int = 0
    caption: Optional[str] = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)

    def to_db(self) -> dict[str, Any]:
        return {
            "table_index": self.table_index,
            "caption": self.caption,
            "data": {"headers": self.headers, "rows": self.rows},
        }


class ResearchRecord(BaseModel):
    """The structured output of the pipeline — one scientific study.

    Fields that the parser/AI may legitimately fail to find are Optional.
    `title` and `url` are the only hard requirements.
    """

    # Core
    title: str
    url: str
    doi: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    publication_date: Optional[date] = None

    # Content
    abstract: Optional[str] = None
    summary: Optional[str] = None
    study_type: Optional[str] = None
    sample_size: Optional[int] = None
    key_findings: list[str] = Field(default_factory=list)
    pdf_links: list[str] = Field(default_factory=list)

    # Tables found on the page
    tables: list[ExtractedTable] = Field(default_factory=list)

    # Provenance / bookkeeping (filled by the pipeline, not the AI)
    source_id: Optional[str] = None
    topic_id: Optional[str] = None
    source_website: str = ""
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    raw_text: Optional[str] = None
    extraction_engine: Optional[str] = None

    # ---- Validators: clean up whatever the AI hands back -----------------

    @field_validator("doi")
    @classmethod
    def _clean_doi(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        # Strip common prefixes like "https://doi.org/" or "doi:".
        v = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", v, flags=re.I).strip()
        return v or None

    @field_validator("publication_date", mode="before")
    @classmethod
    def _parse_date(cls, v: Any) -> Optional[date]:
        if v in (None, "", "null"):
            return None
        if isinstance(v, date):
            return v
        s = str(v).strip()
        # Accept YYYY, YYYY-MM, YYYY-MM-DD and a few common variants.
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y", "%d %b %Y", "%B %d, %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        # Last resort: pull a 4-digit year.
        m = re.search(r"(19|20)\d{2}", s)
        if m:
            return date(int(m.group()), 1, 1)
        return None

    @field_validator("sample_size", mode="before")
    @classmethod
    def _parse_sample_size(cls, v: Any) -> Optional[int]:
        if v in (None, "", "null"):
            return None
        if isinstance(v, int):
            return v
        m = re.search(r"\d[\d,]*", str(v))
        return int(m.group().replace(",", "")) if m else None

    @field_validator("authors", "key_findings", "pdf_links", mode="before")
    @classmethod
    def _ensure_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            # The AI sometimes returns a single string or comma-joined list.
            parts = [p.strip() for p in re.split(r"[;\n]|,(?![^()]*\))", v)]
            return [p for p in parts if p]
        return [str(x).strip() for x in v if str(x).strip()]

    def to_db(self) -> dict[str, Any]:
        """Shape for the research_records table (tables are stored separately)."""
        return {
            "title": self.title,
            "title_normalized": normalize_title(self.title),
            "url": self.url,
            "doi": self.doi,
            "authors": self.authors,
            "publication_date": (
                self.publication_date.isoformat() if self.publication_date else None
            ),
            "abstract": self.abstract,
            "summary": self.summary,
            "study_type": self.study_type,
            "sample_size": self.sample_size,
            "key_findings": self.key_findings,
            "pdf_links": self.pdf_links,
            "source_id": self.source_id,
            "topic_id": self.topic_id,
            "source_website": self.source_website,
            "retrieved_at": self.retrieved_at.isoformat(),
            "raw_text": (self.raw_text or "")[:20000] or None,  # cap stored text
            "extraction_engine": self.extraction_engine,
        }


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for fuzzy dedup."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
