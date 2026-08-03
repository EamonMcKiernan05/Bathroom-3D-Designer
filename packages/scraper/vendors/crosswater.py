"""Crosswater (https://www.crosswater.co.uk/) — PRIORITY 4 (doc 02 §2.1).

Custom CMS. Category pages are JS-rendered (SPA), but product pages are
server-side rendered and the sitemap.xml exposes all ~870 product URLs
(verified 2026-08-03). So we drive crosswater via the sitemap, not the JS
category pages — HTTP-only, no browser needed.

Product page: name, £X RRP price, SKU (e.g. LM3516FSTAN_V2), description,
dimensions, images via Cloudflare CDN (/cdn-cgi/image/...).
"""
from __future__ import annotations

import html as htmlmod
import re

from ..shared.dimensions import extract_dimensions
from ..shared.normalize import normalize_finish
from ..shared.prices import parse_price
from .base import VendorScraper

CATEGORY_MAP = {
    "taps": "taps",
    "showers": "showering",
    "baths": "baths",
    "toilets": "toilets",
    "basins": "basins",
    "vanities": "furniture/vanity-units",
    "furniture": "furniture",
    "mirrors": "mirrors-cabinets/mirrors",
    "accessories": "accessories",
}

_SITEMAP_PROD = re.compile(r"<loc>(https://www\.crosswater\.co\.uk/product/[^<]+)</loc>")
_SKU = re.compile(r"\b([A-Z]{2,}\d{2,}[A-Z0-9_\-]*)\b")
_WIDTH = re.compile(r"Width\s*[:]?\s*(\d+(?:\.\d+)?)\s*mm", re.I)
_HEIGHT = re.compile(r"Height\s*[:]?\s*(\d+(?:\.\d+)?)\s*mm", re.I)
_DEPTH = re.compile(r"Depth\s*[:]?\s*(\d+(?:\.\d+)?)\s*mm", re.I)
_IMG = re.compile(r'(?:src|data-src)="([^"]+/cdn-cgi/image/[^"]+)"', re.I)
_IMG_ALT = re.compile(r'(?:src|data-src)="([^"]*api/product-assets/file/[^"]+)"', re.I)


class CrosswaterScraper(VendorScraper):
    slug = "crosswater"
    base_url = "https://www.crosswater.co.uk"
    start_categories = [("all", "/sitemap.xml")]  # sitemap drives URL discovery
    CATEGORY_MAP = CATEGORY_MAP

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        # category_url is the sitemap; pull product URLs from it
        return [m.group(1) for m in _SITEMAP_PROD.finditer(html)]

    def extract_product(self, html: str, url: str) -> dict | None:
        text = htmlmod.unescape(html)

        m = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
        name = htmlmod.unescape(m.group(1)).split("|")[0].strip() if m else None
        if not name:
            return None

        # price
        price = parse_price(text)

        # SKU — uppercase token near the product area
        sku = None
        m = re.search(r"\b([A-Z]{2,}\d{2,}[A-Z0-9_\-]{3,})\b", text)
        if m:
            sku = m.group(1)

        # dimensions — labelled fields
        dims = {"width_mm": None, "height_mm": None, "depth_mm": None, "diameter_mm": None}
        hits = 0
        for key, pat in (("width_mm", _WIDTH), ("height_mm", _HEIGHT), ("depth_mm", _DEPTH)):
            m = pat.search(text)
            if m:
                dims[key] = float(m.group(1))
                hits += 1
        confidence = "high" if hits >= 2 else ("medium" if hits == 1 else None)

        # finish from description
        finish = None
        m = re.search(r"(Chrome|Brushed Brass|Brushed Nickel|Matt Black|Anthracite|Gunmetal|Polished Chrome)", text, re.I)
        if m:
            finish = normalize_finish(m.group(1))

        # images — Cloudflare CDN URLs
        imgs = []
        seen = set()
        for pat in (_IMG, _IMG_ALT):
            for m in pat.finditer(text):
                u = m.group(1)
                if u in seen:
                    continue
                seen.add(u)
                imgs.append(u)
        if not imgs:
            m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', text, re.I)
            if m:
                imgs.append(m.group(1))

        return {
            "retailer_sku": sku or url.rstrip("/").rsplit("/", 1)[-1],
            "retailer_url": url,
            "name": name.strip(),
            "brand": "Crosswater",
            "description": None,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"] or "RRP",
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [finish] if finish else [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": None,
            "category_key": "all",
        }