"""MyLife Bathrooms (https://mylifebathrooms.com/) — PRIORITY 3 (doc 02 §2.2).

Magento 2 (Adobe Commerce). Category pages are JS-rendered; the REST API is
auth-gated (401, verified 2026-08-03) so the browser path is required.
Product pages are SSR once you have the URLs.

Requires: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import html as htmlmod
import re

from ..shared.browser import fetch_js
from ..shared.dimensions import extract_dimensions
from ..shared.normalize import normalize_finish
from ..shared.prices import parse_price
from .base import VendorScraper

CATEGORY_MAP = {
    "furniture": "furniture",
    "vanity-units": "furniture/vanity-units",
    "mirrors-cabinets": "mirrors-cabinets",
    "mirrors": "mirrors-cabinets/mirrors",
    "taps-accessories": "taps",
    "basins": "basins",
    "ceramics": "toilets",
    "bathing": "baths",
    "showering": "showering",
    "heated-towel-rails": "heating/towel-rails",
    "fitted-furniture": "furniture/fitted-furniture",
    "accessories": "accessories",
}

# product links: https://mylifebathrooms.com/{category}/{product-slug}/
_PROD_LINK = re.compile(r'href="(https://mylifebathrooms\.com/[a-z0-9-]+/[a-z0-9-]+/)"', re.I)
_SKU = re.compile(r"SKU\s*[:]?\s*([A-Za-z0-9][A-Za-z0-9._\-]*)", re.I)
_CAT = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_IMG = re.compile(r'(?:src|data-src)="(https://mylifebathrooms\.com/media/catalog/[^"]+)"', re.I)


class MyLifeScraper(VendorScraper):
    slug = "mylife"
    base_url = "https://mylifebathrooms.com"
    uses_js = True
    start_categories = [
        ("furniture", "/furniture/"),
        ("vanity-units", "/furniture/vanity-units/"),
        ("mirrors-cabinets", "/mirrors-cabinets/"),
        ("taps-accessories", "/taps-accessories/"),
        ("basins", "/basins/"),
        ("ceramics", "/ceramics/"),
        ("bathing", "/bathing/"),
        ("showering", "/showering/"),
        ("heated-towel-rails", "/heated-towel-rails/"),
        ("fitted-furniture", "/fitted-furniture/"),
        ("accessories", "/accessories/"),
    ]
    CATEGORY_MAP = CATEGORY_MAP

    def fetch_js(self, url: str) -> str | None:
        return fetch_js(url, wait_selector=".product-item, .products, .product-grid, main")

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls = []
        for m in _PROD_LINK.finditer(html):
            u = m.group(1)
            # skip category nav pages that also match the 2-segment pattern
            if u.rstrip("/").rsplit("/", 1)[-1] in ("furniture", "mirrors-cabinets", "taps-accessories", "basins", "ceramics", "bathing", "showering", "heated-towel-rails", "fitted-furniture", "accessories"):
                continue
            if u not in urls:
                urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        text = htmlmod.unescape(html)
        m = _CAT.search(text)
        name = htmlmod.unescape(m.group(1)).split("|")[0].strip() if m else None
        if not name:
            return None

        sku = None
        m = _SKU.search(text)
        if m:
            sku = m.group(1).strip()

        price = parse_price(text)
        dims = extract_dimensions(text, vendor=None)
        confidence = dims.pop("confidence")

        finish = None
        m = re.search(r"(Chrome|Matt Black|Brushed Brass|Brushed Nickel|Gunmetal|White|Anthracite|Polished Nickel)", text, re.I)
        if m:
            finish = normalize_finish(m.group(1))

        imgs = []
        seen = set()
        for m in _IMG.finditer(text):
            u = m.group(1)
            # skip placeholder images
            if "placeholder" in u.lower() or "noimage" in u.lower():
                continue
            if u not in seen:
                seen.add(u)
                imgs.append(u)

        return {
            "retailer_sku": sku or url.rstrip("/").rsplit("/", 1)[-1],
            "retailer_url": url,
            "name": name.strip(),
            "brand": "MyLife",
            "description": None,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"],
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [finish] if finish else [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": None,
            "category_key": None,
        }