"""Whole Foods deals collector.

Whole Foods isn't on Flipp, but its own site exposes the weekly sales as JSON
(no bot wall). We read the Next.js data endpoint for the configured store and
write the promotions into grocery_deals (store = "Whole Foods").

Endpoint shape (discovered by inspecting wholefoodsmarket.com):
  buildId:  homepage HTML -> "buildId":"<id>"
  sales:    /_next/data/<buildId>/sales-flyer.json?store-id=<storeId>
            -> pageProps.promotions[]  (productName, salePrice, primePrice,
               regularPrice, headline, endDate, productImage, originBrandName...)

Prices are human strings like "$3.99/lb", so we parse the numeric part and keep
the original text in `discount` for full context (per-lb, "with Prime", etc.).

Because the weekly flyer fully refreshes, this collector REPLACES all existing
Whole Foods rows each run (delete-then-insert), rather than de-duping by id.
"""
from __future__ import annotations

import re
from typing import Any, Optional

import requests

from ..config import settings
from ..db import Database
from ..logging_conf import get_logger

log = get_logger(__name__)

WFM_BASE = "https://www.wholefoodsmarket.com"
STORE_LABEL = "Whole Foods"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0 Safari/537.36",
    "Accept": "application/json,text/html",
}
_MULTI_RE = re.compile(r"(\d+)\s*for\s*\$\s*(\d+(?:\.\d{1,2})?)", re.I)
_DOLLAR_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")


def _get(url: str, **kw) -> requests.Response:
    last: Optional[Exception] = None
    for attempt in range(1, settings.max_retries + 1):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=settings.http_timeout, **kw)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
    assert last is not None
    raise last


def _build_id() -> str:
    html = _get(f"{WFM_BASE}/").text
    m = re.search(r'"buildId":"([^"]+)"', html)
    if not m:
        raise RuntimeError("Could not find Whole Foods buildId")
    return m.group(1)


def _parse_price(*values: Any) -> Optional[float]:
    """Best numeric price from messy strings.

    Handles "$3.99/lb" -> 3.99, "2 for $8" -> 4.00 (per unit), and returns None
    for things with no dollar amount like "Buy 1, Get 1 Free".
    """
    for v in values:
        if not v:
            continue
        s = str(v)
        m = _MULTI_RE.search(s)          # "N for $M" -> per-unit price
        if m:
            n, total = int(m.group(1)), float(m.group(2))
            return round(total / n, 2) if n else total
        m = _DOLLAR_RE.search(s)         # plain "$X" (require the $ sign)
        if m:
            return float(m.group(1))
    return None


def _normalize(promo: dict[str, Any]) -> dict[str, Any]:
    name = (promo.get("productName") or "").strip() or "(unnamed item)"
    size = (promo.get("packageSize") or "").strip()
    if size:
        name = f"{name} ({size})"

    sale = promo.get("salePrice")
    prime = promo.get("primePrice")
    # Headline/price text keeps per-lb + "with Prime" nuance the number can't.
    parts = []
    if prime:
        parts.append(f"Prime {prime}")
    if sale and sale != prime:
        parts.append(f"Sale {sale}")
    discount = " / ".join(parts) or (promo.get("headline") or None)

    return {
        "flipp_item_id": None,
        "store": STORE_LABEL,
        "merchant_raw": "Whole Foods Market",
        "product_name": name,
        "brand": (promo.get("originBrandName") or None),
        "price": _parse_price(prime, sale),   # advertised (Prime) price first
        "discount": discount,
        "valid_from": promo.get("startDate"),
        "valid_to": promo.get("endDate"),
        "image_url": promo.get("productImage"),
        "flyer_id": None,
        "postal_code": settings.wfm_postal_code,
    }


def collect_into(db: Database, run_id: str) -> dict[str, int]:
    """Pull Whole Foods sales for the configured store into grocery_deals.

    Gated by the "Whole Foods" row in grocery_stores (toggle it in /admin).
    Returns stats. Does NOT create/finish the run (the coordinator does).
    """
    stores = db.get_enabled_stores()
    enabled = any(
        s.get("display_name") == STORE_LABEL or s.get("match_key") == "wholefoods-api"
        for s in stores
    )
    if not enabled:
        log.info("Whole Foods store disabled — skipping.")
        return {"flyers": 0, "found": 0, "new": 0, "errors": 0}

    store_id = settings.wfm_store_id
    log.info("Whole Foods collect: store %s", store_id)
    try:
        build = _build_id()
        data = _get(
            f"{WFM_BASE}/_next/data/{build}/sales-flyer.json",
            params={"store-id": store_id},
        ).json()
        promos = data.get("pageProps", {}).get("promotions", [])
    except Exception as e:  # noqa: BLE001
        db.log_error(run_id, None, f"wfm store {store_id}", "wholefoods", e)
        return {"flyers": 0, "found": 0, "new": 0, "errors": 1}

    rows = [_normalize(p) for p in promos]
    found = len(rows)

    try:
        # Weekly flyer fully refreshes -> replace this store's rows.
        db.client.table("grocery_deals").delete().eq("store", STORE_LABEL).execute()
        new = db.insert_deals(rows)
    except Exception as e:  # noqa: BLE001
        db.log_error(run_id, None, "wfm insert", "db", e)
        return {"flyers": 1, "found": found, "new": 0, "errors": 1}

    log.info("Whole Foods: %d promotions, %d stored", found, new)
    return {"flyers": 1, "found": found, "new": new, "errors": 0}
