"""Genesis Global Systems (https://www.genesis-gs.com/) — PRIORITY 2 (doc 02 §2.4).

WordPress + WooCommerce, server-side rendered. Categories: kitchen-and-bathroom,
tile-edging, floor-trims-and-transitions. Products: name, SKU, category,
description, images. Prices are often option-based (variable products) so
price_gbp is usually null — extracted when present.

Relevant subset: tile edging trims, floor transitions, shower channels.
"""
from __future__ import annotations

import html as htmlmod
import json
import re

from ..shared.dimensions import extract_dimensions
from ..shared.prices import parse_price
from .base import VendorScraper

CATEGORY_MAP = {
    "kitchen-and-bathroom": "tiles-panels",
    "tile-edging": "tiles-panels/tile-edging",
    "floor-trims-and-transitions": "tiles-panels/floor-trims",
    "shower-channels": "tiles-panels/shower-channels",
    "corner-protectors": "tiles-panels/tile-edging",
    "waterproofing-membranes": "tiles-panels/waterproofing",
}

_PROD_LINK = re.compile(r'href="(https://www\.genesis-gs\.com/product/[^"]+/)"', re.I)
_SKU = re.compile(r"SKU\s*:\s*([A-Za-z0-9][A-Za-z0-9.\-]*)", re.I)
_BREADCRUMB = re.compile(r"Home\s*/\s*([^/]+)/\s*([^/]+)/\s*([^/]+?)\s*$", re.I)
_IMG = re.compile(r'data-src="(https://www\.genesis-gs\.com/wp-content/uploads/[^"]+\.(?:png|jpg|jpeg|webp))"', re.I)
_ID = re.compile(r"<h1[^>]*class=\"[^\"]*product_title[^\"]*\"[^>]*>(.*?)</h1>", re.I | re.S)


class GenesisScraper(VendorScraper):
    slug = "genesis"
    base_url = "https://www.genesis-gs.com"
    start_categories = [
        ("kitchen-and-bathroom", "/product-category/kitchen-and-bathroom/"),
        ("tile-edging", "/product-category/tile-edging/"),
        ("floor-trims-and-transitions", "/product-category/floor-trims-and-transitions/"),
        ("shower-channels", "/product-category/shower-channels/"),
    ]
    CATEGORY_MAP = CATEGORY_MAP

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls = []
        for m in _PROD_LINK.finditer(html):
            u = m.group(1)
            if u not in urls:
                urls.append(u)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        text = htmlmod.unescape(html)

        # name from <h1 product_title>
        name = None
        m = _ID.search(text)
        if m:
            name = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if not name:
            m = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
            if m:
                name = htmlmod.unescape(m.group(1)).split("|")[0]
                name = re.sub(r"\s*-\s*Genesis Global Systems\s*$", "", name).strip()
        if not name:
            return None
        name = re.sub(r"\s+", " ", name).strip()

        sku = None
        m = _SKU.search(text)
        if m:
            sku = m.group(1).strip()

        # category from breadcrumb
        cat_key = None
        m = _BREADCRUMB.search(text)
        if m:
            cat_key = m.group(2).strip().lower().replace(" ", "-")

        # description (product description block)
        desc = None
        m = re.search(r'<div[^>]*class="[^"]*woocommerce-Tabs-panel[^"]*"[^>]*>(.*?)</div>', text, re.I | re.S)
        if m:
            desc = re.sub(r"<[^>]+>", " ", m.group(1))
            desc = re.sub(r"\s+", " ", desc).strip()

        dims = extract_dimensions(f"{name} {desc or ''}", vendor=None)
        confidence = dims.pop("confidence")

        # price (variable products often omit)
        price = parse_price(text)

        # images — main product image (non-swatch)
        imgs = []
        for m in _IMG.finditer(text):
            u = m.group(1)
            if "swatch" in u.lower() or "logo" in u.lower() or ".svg" in u:
                continue
            imgs.append(u)
        if not imgs:
            m = re.search(r'class="[^"]*woocommerce-product-gallery__image[^"]*"[^>]*data-thumb="([^"]+)"', text)
            if m:
                imgs.append(m.group(1))

        return {
            "retailer_sku": sku or url.rstrip("/").rsplit("/", 1)[-1],
            "retailer_url": url,
            "name": name,
            "brand": "Genesis",
            "description": desc,
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
            "category_key": cat_key,
        }