"""City Plumbing (https://www.cityplumbing.co.uk/) — LAST PRIORITY (doc 02 §2.3).

Massive site (30k+ products). Scoped to bathroom subcategories only, JS-rendered
(React/Next.js), conservative delays (5s+). Only run once the scraper is proven
on other sites (Phase 6.2 / Phase 8 per Final Review).

Product page: /p/{name}/p/{productId}. Category: /c/product/bathrooms/c/{id}/.
Requires `pip install playwright && playwright install chromium`.
"""
from __future__ import annotations

import html as htmlmod
import random
import re
import time

from ..shared.browser import fetch_js
from ..shared.dimensions import extract_dimensions
from ..shared.prices import parse_price
from .base import VendorScraper

CATEGORY_MAP = {
    "baths": "baths",
    "toilets": "toilets",
    "basins": "basins",
    "showers": "showering",
    "furniture": "furniture",
    "taps": "taps",
    "radiators": "heating",
    "tiles": "tiles-panels",
}

# product page: /p/{slug}/p/{id}
_PROD_LINK = re.compile(r'href="(/p/[^"]+/p/\d+)"', re.I)
_SKU = re.compile(r"SKU\s*[:]?\s*([A-Za-z0-9][A-Za-z0-9._\-]*)", re.I)
_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_IMG = re.compile(r'(?:src|data-src)="(https://images\.ctfassets\.net/[^"]+)"', re.I)


class CityPlumbingScraper(VendorScraper):
    slug = "city-plumbing"
    base_url = "https://www.cityplumbing.co.uk"
    uses_js = True
    start_categories = [
        ("baths", "/c/product/bathrooms/baths/c/1800003/"),
        ("toilets", "/c/product/bathrooms/toilets/c/1800004/"),
        ("basins", "/c/product/bathrooms/basins/c/1800005/"),
        ("showers", "/c/product/bathrooms/showers/c/1800006/"),
        ("furniture", "/c/product/bathrooms/furniture/c/1800007/"),
        ("taps", "/c/product/bathrooms/taps/c/1800008/"),
        ("radiators", "/c/product/bathrooms/radiators/c/1800009/"),
    ]
    CATEGORY_MAP = CATEGORY_MAP

    def fetch_js(self, url: str) -> str | None:
        html = fetch_js(url, wait_selector="main, .product, .grid", timeout_ms=45000)
        # conservative 5s+ delay for this large site (doc 02 §2.3)
        time.sleep(random.uniform(5.0, 7.0))
        return html

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls = []
        for m in _PROD_LINK.finditer(html):
            u = m.group(1)
            if u not in urls:
                urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        text = htmlmod.unescape(html)
        m = _TITLE.search(text)
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

        imgs = []
        seen = set()
        for m in _IMG.finditer(text):
            u = m.group(1)
            if u not in seen:
                seen.add(u)
                imgs.append(u)

        return {
            "retailer_sku": sku or url.rstrip("/").rsplit("/", 1)[-1],
            "retailer_url": url,
            "name": name.strip(),
            "brand": None,
            "description": None,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"],
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": None,
            "category_key": None,
        }