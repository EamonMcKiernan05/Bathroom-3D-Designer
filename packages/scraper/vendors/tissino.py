"""Tissino (https://www.tissino.co.uk/) — sitemap + JSON-LD scrape.

Every product page carries a complete schema.org Product block (name,
description, sku, price GBP, availability, image) — no JS needed. Product
URLs come from the 10 product sitemaps listed in sitemap.xml (458 total).
The sitemap segment doubles as the source category.
"""
from __future__ import annotations

import html as htmlmod
import json
import re

from ..shared.dimensions import extract_dimensions
from ..shared.prices import parse_price
from .base import VendorScraper

BASE = "https://www.tissino.co.uk"

# sitemap segment -> normalized category (shared taxonomy where possible)
_SEGMENT_CATEGORY = {
    "accessories": "accessories",
    "bathing": "baths",
    "brassware": "taps",
    "furniture": "furniture",
    "heating": "heating/towel-rails",
    "mirrorsAndCabinets": "mirrors-cabinets",
    "sanitaryware": "toilets",
    "showering": "showering",
    "showeringBrassware": "showering",
    # 'samples' segment excluded — finish sample packs, not products
}

# hidden plumbing / small parts stay generic (user scope rule)
_EXCLUDE_RE = re.compile(
    r"\bwastes?\b|\boverflows?\b|\btraps?\b|\bpipework?\b|\bdrains?\b|"
    r"\bseals?\b|\bfixing\b|\bshelf\b|\bshelving\b",
    re.I,
)

_JSONLD = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.I | re.S)


class TissinoScraper(VendorScraper):
    slug = "tissino"
    base_url = BASE
    start_categories = [("all", "/sitemap.xml")]
    # category_key on each product already carries the normalized slug
    CATEGORY_MAP = {v: v for v in set(_SEGMENT_CATEGORY.values())} | {
        "all": "tissino/uncategorised",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._url_category: dict[str, str] = {}

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        """Enumerate product URLs from the product sub-sitemaps and record
        each URL's source segment for attribution."""
        urls, seen = [], set()
        for seg, cat in _SEGMENT_CATEGORY.items():
            sub = f"{self.base_url}/sitemaps-1-product-{seg}-1-sitemap.xml"
            body = self.http.fetch_html(sub)
            if not body:
                continue
            for u in re.findall(r"<loc>([^<]+)</loc>", body):
                u = u.strip()
                if u in seen:
                    continue
                seen.add(u)
                self._url_category[u.rstrip("/")] = cat
                urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        # pull the schema.org Product block
        prod = None
        for ld in _JSONLD.findall(html):
            try:
                d = json.loads(ld)
            except ValueError:
                continue
            items = d.get("@graph", d) if isinstance(d, dict) else d
            if not isinstance(items, list):
                items = [items]
            for it in items:
                if isinstance(it, dict) and it.get("@type") == "Product":
                    prod = it
                    break
            if prod:
                break
        if not prod:
            return None

        name = htmlmod.unescape(prod.get("name", "")).strip()
        if not name:
            return None
        if _EXCLUDE_RE.search(name):
            return None

        # price
        price = {"price_gbp": None, "price_note": None, "price_is_from": False}
        offers = prod.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        raw = offers.get("price")
        if raw is not None:
            try:
                price["price_gbp"] = round(float(str(raw).replace(",", "")), 2)
            except ValueError:
                price = parse_price(str(raw))
        availability = str(offers.get("availability", ""))
        in_stock = "InStock" in availability or availability == ""

        # image
        imgs = []
        img = prod.get("image")
        if isinstance(img, dict):
            img = img.get("url")
        if img:
            imgs.append(img)

        # description (may hold dimensions like "600mm")
        desc = prod.get("description")
        if desc:
            desc = htmlmod.unescape(str(desc))[:2000]
        dims = extract_dimensions(desc or "", vendor=None)
        confidence = dims.pop("confidence")

        cat = self._url_category.get(url.rstrip("/"), "all")

        return {
            "retailer_sku": prod.get("sku") or url.rstrip("/").rsplit("/", 1)[-1],
            "retailer_url": url,
            "name": name,
            "brand": "Tissino",
            "description": desc,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"],
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs[:3],
            "in_stock": in_stock,
            "category_key": cat,
        }
