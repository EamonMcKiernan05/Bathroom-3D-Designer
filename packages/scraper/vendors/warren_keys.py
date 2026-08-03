"""Warren Keys Isle of Man (https://wkbom.im/) — PRIORITY 5 (doc 02 §2.5).

This is a TILE SUPPLIER whose "products" are tile collections in PDF brochures
— no structured product pages. Per the plan (doc 02 §2.5 + Final Review #3):
manually curate 20-30 popular tile ranges from their brochures and load them
into the products table. No live scrape.

This vendor's `run()` is a loader, not a crawler: it ingests a curated rows
file (JSON or CSV) via `--curated <path>`. Each row is a tile-range product
(name, sku, price, dimensions, image_url, colour family, finish).
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from ..shared import db as dbapi
from ..shared.normalize import normalize_colour, normalize_finish
from .base import VendorScraper

log = logging.getLogger("scraper.warren_keys")

CATEGORY_MAP = {
    "wall-tiles": "tiles-panels/wall-tiles",
    "floor-tiles": "tiles-panels/floor-tiles",
    "multiboard-panels": "tiles-panels/multiboard-panels",
    "shower-wall-panels": "tiles-panels/shower-wall-panels",
}

# Minimal required fields per curated row.
REQUIRED = ("name", "sku", "category")


class WarrenKeysLoader(VendorScraper):
    slug = "warren-keys"
    base_url = "https://wkbom.im"
    start_categories = []  # not a crawler
    CATEGORY_MAP = CATEGORY_MAP

    def __init__(self, dry_run: bool = False, limit: int | None = None, categories=None, curated=None):
        super().__init__(dry_run=dry_run, limit=limit, categories=categories)
        self.curated = curated

    def run(self):
        if not self.curated:
            raise RuntimeError(
                "warren-keys is a manual-curation loader (no live scrape). "
                "Pass --curated <rows.json|rows.csv> with tile ranges you curated "
                "from the brochures (see doc 02 §2.5)."
            )
        rows = self._read_rows(self.curated)
        retailer_id = dbapi.get_retailer_id(self.slug)
        if retailer_id is None:
            raise RuntimeError("Retailer 'warren-keys' not in DB — run app.seed first.")
        db = None if self.dry_run else dbapi.SessionLocal()
        try:
            for row in rows:
                if self.limit and self.stats["found"] >= self.limit:
                    break
                self.stats["found"] += 1
                self._ingest(row, db, retailer_id)
            if db:
                db.commit()
        finally:
            if db:
                db.close()
        return self.stats

    def _read_rows(self, path: str) -> list[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"curated file not found: {p}")
        if p.suffix.lower() == ".csv":
            with open(p, newline="", encoding="utf-8-sig") as f:
                return list(csv.DictReader(f))
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("products", [])

    def _ingest(self, row: dict, db, retailer_id: int):
        missing = [k for k in REQUIRED if not row.get(k)]
        if missing:
            self.errors.append(f"row missing {missing}: {row}")
            self.stats["failed"] += 1
            return
        cat_key = row.get("category", "wall-tiles")
        category_slug, cat_name = self.map_category(cat_key)
        cat_id = None
        if not self.dry_run:
            cat_id = dbapi.get_or_create_category(db, category_slug, cat_name)

        product = {
            "retailer_sku": str(row["sku"]),
            "retailer_url": row.get("url") or f"https://wkbom.im/catalogues/",
            "name": row["name"],
            "brand": row.get("brand", "Warren Keys"),
            "description": row.get("description"),
            "price_gbp": float(row["price"]) if row.get("price") else None,
            "price_note": row.get("price_note"),
            "price_is_from": False,
            "width_mm": float(row["width_mm"]) if row.get("width_mm") else None,
            "height_mm": float(row["height_mm"]) if row.get("height_mm") else None,
            "depth_mm": float(row["depth_mm"]) if row.get("depth_mm") else None,
            "diameter_mm": None,
            "dimensions_confidence": row.get("dimensions_confidence", "high"),
            "finishes": [normalize_finish(row["finish"])] if row.get("finish") else [],
            "colours": [normalize_colour(row["colour"])] if row.get("colour") else [],
            "sizes": [],
            "image_urls": [row["image_url"]] if row.get("image_url") else [],
            "in_stock": True,
        }
        self._persist(product, cat_key, db, retailer_id)