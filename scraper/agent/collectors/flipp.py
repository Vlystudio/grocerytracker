"""Flipp grocery-deals collector.

Pulls weekly flyer deals (product, price, validity) for your whitelisted stores
across your configured ZIP codes, de-duplicates by Flipp item id, and writes
them to the grocery_deals table. Run + error stats reuse scrape_runs/errors.

Flipp endpoints (public backend used by flipp.com):
  GET /flipp/flyers?postal_code=ZIP&locale=en-us       -> list of flyers
  GET /flipp/flyers/{flyer_id}?locale=en-us            -> { items: [...] }
"""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from ..config import settings
from ..db import Database
from ..logging_conf import get_logger
from .enrich import categorize, parse_unit

log = get_logger(__name__)

FLIPP_BASE = "https://backflipp.wishabi.com/flipp"
_HEADERS = {"User-Agent": settings.user_agent or "Mozilla/5.0"}


def _get(url: str, params: dict[str, Any]) -> Any:
    """GET JSON with simple retry/backoff for transient failures."""
    last: Optional[Exception] = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            r = requests.get(url, params=params, headers=_HEADERS, timeout=settings.http_timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(min(2 ** attempt, 15))
    assert last is not None
    raise last


def get_flyers(postal_code: str) -> list[dict[str, Any]]:
    data = _get(f"{FLIPP_BASE}/flyers", {"postal_code": postal_code, "locale": "en-us"})
    return data.get("flyers", []) if isinstance(data, dict) else []


def get_flyer_items(flyer_id: int) -> list[dict[str, Any]]:
    data = _get(f"{FLIPP_BASE}/flyers/{flyer_id}", {"locale": "en-us"})
    return data.get("items", []) if isinstance(data, dict) else []


def _match_store(merchant: str, stores: list[dict[str, Any]]) -> Optional[str]:
    """Return the whitelisted store's display_name if merchant matches, else None."""
    m = (merchant or "").lower()
    for s in stores:
        if s["match_key"] in m:
            return s["display_name"]
    return None


def _to_price(value: Any) -> Optional[float]:
    if value in (None, "", 0, "0"):
        return None
    try:
        return float(str(value).replace("$", "").strip())
    except ValueError:
        return None


def _normalize(item: dict[str, Any], store: str, merchant_raw: str, postal_code: str) -> dict[str, Any]:
    name = (item.get("name") or "").strip() or "(unnamed item)"
    brand = item.get("brand") or None
    category, is_grocery = categorize(name, brand)
    return {
        "flipp_item_id": item.get("id"),
        "store": store,
        "merchant_raw": merchant_raw,
        "product_name": name,
        "brand": brand,
        "price": _to_price(item.get("price")),
        "discount": (item.get("discount") or None),
        "category": category,
        "unit": parse_unit(name),
        "is_grocery": is_grocery,
        "valid_from": item.get("valid_from"),
        "valid_to": item.get("valid_to"),
        "image_url": item.get("cutout_image_url"),
        "flyer_id": item.get("flyer_id"),
        "postal_code": postal_code,
    }


def collect_into(db: Database, run_id: str) -> dict[str, int]:
    """Pull Flipp deals for every enabled location + whitelisted store.

    Does NOT create/finish the run (the coordinator in __init__.py does that so
    Flipp + Whole Foods can share one run). Returns stats.
    """
    locations = db.get_enabled_locations()
    stores = db.get_enabled_stores()
    existing_ids = db.load_deal_ids()

    flyers_processed = 0
    deals_found = 0
    deals_new = 0
    errors = 0
    seen_flyers: set[int] = set()      # a flyer is shared across nearby ZIPs
    new_ids: set[int] = set()           # avoid dupes within this run

    if not stores:
        log.warning("No enabled stores in grocery_stores — nothing to collect.")
    log.info(
        "Grocery collect: %d location(s), %d store(s) whitelisted",
        len(locations),
        len(stores),
    )

    for loc in locations:
        zip_code = loc["postal_code"]
        try:
            flyers = get_flyers(zip_code)
        except Exception as e:  # noqa: BLE001
            db.log_error(run_id, None, f"flyers?postal_code={zip_code}", "flipp", e)
            errors += 1
            continue

        for flyer in flyers:
            store = _match_store(flyer.get("merchant", ""), stores)
            if not store:
                continue
            fid = flyer.get("id")
            if fid in seen_flyers:       # already pulled this flyer for another ZIP
                continue
            seen_flyers.add(fid)

            try:
                items = get_flyer_items(fid)
            except Exception as e:  # noqa: BLE001
                db.log_error(run_id, None, f"flyers/{fid}", "flipp", e)
                errors += 1
                continue

            flyers_processed += 1
            rows = []
            for item in items:
                iid = item.get("id")
                if iid is None:
                    continue
                deals_found += 1
                if iid in existing_ids or iid in new_ids:
                    continue
                new_ids.add(iid)
                rows.append(_normalize(item, store, flyer.get("merchant", ""), zip_code))

            try:
                inserted = db.insert_deals(rows)
                deals_new += inserted
                if inserted:
                    log.info("%s (ZIP %s): +%d new deals", store, zip_code, inserted)
            except Exception as e:  # noqa: BLE001
                db.log_error(run_id, None, f"insert flyer {fid}", "db", e)
                errors += 1

            time.sleep(settings.default_rate_limit)  # politeness

    log.info(
        "Flipp collect done: %d flyers, %d deals seen, %d new, %d errors",
        flyers_processed,
        deals_found,
        deals_new,
        errors,
    )
    return {
        "flyers": flyers_processed,
        "found": deals_found,
        "new": deals_new,
        "errors": errors,
    }
