"""EastBrook (https://www.eastbrooktrade.com/) — full-site sitemap scrape.

Symphony Commerce shop, fully server-rendered (verified 2026-08-05):
product pages carry title, £ price, SKU, shopcdn images, and dims in the
title ("600 x 470"). Sitemap has ~10k URLs; product URLs are exactly
two segments (/category-slug/product-slug). Small-parts categories
(cover caps, plates, spare valves) are excluded per the scope rule.
"""
from __future__ import annotations

import html as htmlmod
import re

from ..shared.dimensions import extract_dimensions
from .base import VendorScraper

BASE = "https://www.eastbrooktrade.com"

# sitemap top segment -> category (None = exclude, small/hidden parts)
_SEGMENT_CATEGORY = {
    "aluminium-range-radiators": "heating/radiators",
    "designer-range-radiators": "heating/radiators",
    "traditional-range-radiators": "heating/radiators",
    "compact-panel-range-radiators": "heating/radiators",
    "clearance-designer-range-radiators": "heating/radiators",
    "clearance-traditional-range-radiators": "heating/radiators",
    "all-electric-range-radiators": "heating/radiators",
    "designer-range-towel-rails": "heating/towel-rails",
    "traditional-range-towel-rails": "heating/towel-rails",
    "multirail-range-towel-rails": "heating/towel-rails",
    "stainless-steel-range-towel-rails": "heating/towel-rails",
    "all-electric-range-towel-rails": "heating/towel-rails",
    "clearance-designer-range-towel-rails": "heating/towel-rails",
    "clearance-multirail-range-towel-rails": "heating/towel-rails",
    "clearance-stainless-steel-range-towel-rails": "heating/towel-rails",
    "towel-rails-py0pyo": "heating/towel-rails",
    "walk-in-shower-enclosures": "showering/shower-enclosures",
    "offset-quad-shower-enclosures": "showering/shower-enclosures",
    "quadrant-shower-enclosures": "showering/shower-enclosures",
    "sliding-shower-doors": "showering/shower-enclosures",
    "hinged-shower-doors": "showering/shower-enclosures",
    "pivot-shower-doors": "showering/shower-enclosures",
    "bi-fold-shower-doors": "showering/shower-enclosures",
    "shower-side-panels": "showering/shower-screens",
    "bath-screens": "showering/shower-screens",
    "rectangular-shower-trays": "showering/shower-trays",
    "square-shower-trays": "showering/shower-trays",
    "quadrant-shower-trays": "showering/shower-trays",
    "offset-quadrant-shower-trays": "showering/shower-trays",
    "pentagon-shower-trays": "showering/shower-trays",
    "single-ended-baths-eev91l": "baths/single-ended",
    "double-ended-baths": "baths/double-ended",
    "freestanding-baths": "baths/freestanding",
    "shower-baths": "baths/shower-bath",
    # small parts / spares — excluded
    "cover-cap": None,
    "cover-plates": None,
    "towel-hangers-abejs8": "accessories",
}

_TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.I | re.S)
_PRICE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)")
_SKU = re.compile(r'itemprop="sku"[^>]*content="([^"]+)"', re.I)
_IMG = re.compile(r'<img[^>]*src="(https://images\.shopcdn\.co\.uk/[^"]+)"')
_DIMS_TITLE = re.compile(r"(\d{3,4})\s*(?:x|×)\s*(\d{3,4})")


def _segment(url: str) -> str:
    path = url.replace(BASE, "").strip("/")
    return path.split("/")[0] if path else ""


class EastbrookScraper(VendorScraper):
    slug = "eastbrook"
    base_url = BASE
    start_categories = [("all", "/sitemap.xml")]
    CATEGORY_MAP = {v: v for v in set(_SEGMENT_CATEGORY.values()) if v} | {
        "all": "eastbrook/uncategorised",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._url_category: dict[str, str] = {}

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls, seen = [], set()
        prefix = self.base_url + "/"
        for u in re.findall(r"<loc>([^<]+)</loc>", html):
            if not u.startswith(prefix):
                continue
            path = u[len(prefix):].strip("/")
            segs = path.split("/")
            if len(segs) != 2:
                continue  # category pages (1 seg) + deeper paths aren't products
            cat = _SEGMENT_CATEGORY.get(segs[0], "SKIP")
            if cat == "SKIP":
                continue  # unmapped category — don't guess
            if cat is None:
                continue  # excluded small-parts category
            if u in seen:
                continue
            seen.add(u)
            self._url_category[u.rstrip("/")] = cat
            urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        m = _TITLE.search(html)
        if not m:
            return None
        name = htmlmod.unescape(m.group(1)).split("|")[0].strip()
        if not name:
            return None

        sm = _SKU.search(html)
        sku = sm.group(1) if sm else url.rstrip("/").rsplit("/", 1)[-1]
        # URL-slug SKUs can exceed the varchar(100) column — truncate, and
        # sanitize filename-hostile chars (used in the image dir path)
        sku = sku[:100]
        sku = re.sub(r"[^\w\-.]+", "-", sku).strip("-")

        pm = _PRICE.search(html)
        price = float(pm.group(1).replace(",", "")) if pm else None

        # dims from the title first ("600 x 470 ..."), else the page body
        dims = {"width_mm": None, "depth_mm": None, "height_mm": None}
        confidence = None
        dm = _DIMS_TITLE.search(name)
        if dm:
            dims["width_mm"] = int(dm.group(1))
            dims["depth_mm"] = int(dm.group(2))
            confidence = "medium"
        else:
            parsed = extract_dimensions(html[:20000], vendor=None)
            confidence = parsed.pop("confidence")
            dims.update({k: v for k, v in parsed.items() if v})

        imgs, seen_fn = [], set()
        for u in _IMG.findall(html):
            fn = u.rsplit("/", 2)[1] if "/" in u else u
            if fn in seen_fn:
                continue
            seen_fn.add(fn)
            imgs.append(u)
            if len(imgs) >= 3:
                break

        return {
            "retailer_sku": sku,
            "retailer_url": url,
            "name": name,
            "brand": "EastBrook",
            "description": None,
            "price_gbp": price,
            "price_note": None,
            "price_is_from": False,
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": None,
            "category_key": self._url_category.get(url.rstrip("/"), "all"),
        }
