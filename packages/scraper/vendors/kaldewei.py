"""Kaldewei (https://www.kaldewei.co.uk/) — sitemap + SSR scrape.

Small premium catalogue (baths/showers/washbasins). Product URLs from the
three product sub-sitemaps; name from <title>, dimensions from the first
"LxW[xH] mm" on the page, image from files.cdn.kaldewei.com articleimages.
No prices on the site (trade) — price_gbp stays None.
"""
from __future__ import annotations

import html as htmlmod
import re

from ..shared.dimensions import extract_dimensions
from .base import VendorScraper

BASE = "https://www.kaldewei.co.uk"

_SEGMENT_CATEGORY = {
    "baths": "baths",
    "showers": "showering/shower-trays",
    "washbasins": "basins",
}

_TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.I | re.S)
_DIMS = re.compile(r"(\d{3,4})\s*(?:x|×)\s*(\d{3,4})(?:\s*(?:x|×)\s*(\d{3,4}))?\s*mm", re.I)
_ARTICLE_IMG = re.compile(r'https://files\.cdn\.kaldewei\.com/configurator/articleimages/[^"\']+')
_ARTICLE_NO = re.compile(r"articleimages(?:_small)?/(\d+)-(\d+)")


class KaldeweiScraper(VendorScraper):
    slug = "kaldewei"
    base_url = BASE
    start_categories = [("all", "/sitemap.xml")]
    CATEGORY_MAP = {v: v for v in _SEGMENT_CATEGORY.values()} | {"all": "kaldewei/uncategorised"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._url_category: dict[str, str] = {}

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls, seen = [], set()
        for seg, cat in _SEGMENT_CATEGORY.items():
            sub = f"{self.base_url}/sitemap.xml?sitemap={seg}"
            body = self.http.fetch_html(sub)
            if not body:
                continue
            for u in re.findall(r"<loc>([^<]+)</loc>", body):
                u = u.strip()
                if u in seen or "/detail/product/" not in u:
                    continue
                seen.add(u)
                self._url_category[u.rstrip("/")] = cat
                urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        m = _TITLE.search(html)
        if not m:
            return None
        name = htmlmod.unescape(m.group(1).split("|")[0]).strip()
        if not name:
            return None

        # sku from the configurator article image (family-article) or the URL
        sku = None
        am = _ARTICLE_NO.search(html)
        if am:
            sku = f"{am.group(1)}-{am.group(2)}"
        if not sku:
            sku = url.rstrip("/").rsplit("/", 1)[-1].upper()

        # first real dimension pair on the page (spec list is early in DOM)
        dm = _DIMS.search(html)
        dims = {"width_mm": None, "depth_mm": None, "height_mm": None}
        if dm:
            dims["width_mm"] = int(dm.group(1))
            dims["depth_mm"] = int(dm.group(2))
            if dm.group(3):
                dims["height_mm"] = int(dm.group(3))

        imgs = []
        seen_fn = set()
        for u in _ARTICLE_IMG.findall(html):
            fn = u.rsplit("/", 1)[-1]
            if fn in seen_fn:
                continue
            seen_fn.add(fn)
            imgs.append(u)
            if len(imgs) >= 2:
                break

        return {
            "retailer_sku": sku,
            "retailer_url": url,
            "name": name,
            "brand": "Kaldewei",
            "description": None,
            "price_gbp": None,
            "price_note": None,
            "price_is_from": False,
            **dims,
            "dimensions_confidence": "medium" if dims["width_mm"] else None,
            "finishes": [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": None,
            "category_key": self._url_category.get(url.rstrip("/"), "all"),
        }
