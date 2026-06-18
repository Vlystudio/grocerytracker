"""Duplicate detection: URL (exact) -> DOI (exact) -> fuzzy title match.

The fuzzy step catches the common case where the same paper appears at two
URLs / preprint versions with a slightly different title.
"""
from __future__ import annotations

from rapidfuzz import fuzz, process

from .config import settings
from .db import DedupIndex
from .models import ResearchRecord, normalize_title


def find_duplicate_reason(record: ResearchRecord, index: DedupIndex) -> str | None:
    """Return a human-readable reason if `record` duplicates an existing one.

    Returns None if the record looks new.
    """
    # 1. Exact URL match (cheapest, most reliable).
    if record.url in index.urls:
        return "duplicate url"

    # 2. Exact DOI match (authoritative when a DOI exists).
    if record.doi and record.doi in index.dois:
        return f"duplicate doi ({record.doi})"

    # 3. Fuzzy title match against everything we've seen.
    norm = normalize_title(record.title)
    if norm and index.titles:
        match = process.extractOne(
            norm, index.titles, scorer=fuzz.token_sort_ratio
        )
        if match and match[1] >= settings.fuzzy_title_threshold:
            return f"fuzzy title match ({int(match[1])}% ≈ '{match[0][:60]}')"

    return None
