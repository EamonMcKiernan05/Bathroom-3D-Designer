"""Scraper base class — the run loop every vendor implements.

Contract per vendor:
- `slug`, `base_url`, `start_categories` (list of category URLs to crawl)
- `CATEGORY_MAP` — vendor category → normalized taxonomy slug ('' fallback root)
- `list_product_urls(html, category_url) -> list[str]`
- `extract_product(html, url) -> dict | None` (doc 02 §1 ScrapedProduct shape)
- optional `uses_js` — set True and implement `fetch_js(url)` when the site
  needs a real browser (Playwright/scrapling). HTTP-only by default.
"""
from __future__ import annotations

import logging
import time

from .. import config
from ..shared import db as dbapi
from ..shared.http import PoliteSession
from ..shared.images import store_image

log = logging.getLogger("scraper.vendor")


class VendorScraper:
    slug: str = ""
    base_url: str = ""
    start_categories: list[tuple[str, str]] = []  # (vendor cat key, relative URL)
    CATEGORY_MAP: dict[str, str] = {}  # vendor cat key -> normalized slug
    DEFAULT_CATEGORY = "uncategorised"
    uses_js = False

    def __init__(self, dry_run: bool = False, limit: int | None = None, categories: list[str] | None = None, curated=None):
        self.dry_run = dry_run
        self.limit = limit
        self.categories = categories  # subset filter (vendor cat keys)
        self.curated = curated  # only used by manual-curation loaders (warren-keys)
        self.http = PoliteSession(self.base_url)
        self.stats = {"found": 0, "new": 0, "updated": 0, "failed": 0, "skipped": 0}
        self.errors: list[str] = []
        self._recent_urls: set[str] = set()  # resume support, filled in run()

    # -- helpers ---------------------------------------------------------
    def abs_url(self, url: str) -> str:
        from urllib.parse import urljoin

        return urljoin(self.base_url + "/", url)

    def map_category(self, vendor_key: str | None) -> tuple[str, str | None]:
        """Return (normalized_category_slug, display_name) for a vendor category key."""
        if not vendor_key:
            return self.DEFAULT_CATEGORY, None
        slug = self.CATEGORY_MAP.get(vendor_key)
        if slug:
            return slug, None
        # vendor-specific fallback: <vendor>/<vendor-key> (doc 02 §6.4)
        return f"{self.slug}/{vendor_key}", vendor_key.replace("-", " ").title()

    # -- to override -----------------------------------------------------
    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        raise NotImplementedError

    def extract_from_category(self, html: str, category_url: str) -> list[dict] | None:
        """Optional: extract product rows DIRECTLY from the category page.

        Return a list of extract_product-shaped dicts to persist them without
        visiting individual product pages (brochure directories, curated
        listing pages with no detail pages). Return None to fall back to the
        normal list_product_urls + per-product fetch loop.
        """
        return None

    def extract_product(self, html: str, url: str) -> dict | None:
        """Return doc 02 §1 ScrapedProduct-shaped dict (minus retailer fields) or None."""
        raise NotImplementedError

    def fetch_js(self, url: str) -> str | None:
        """Real-browser fetch (doc 00 §8.4). Override in JS-required vendors."""
        raise NotImplementedError("vendor requires JS — implement fetch_js")

    def fetch(self, url: str) -> str | None:
        return self.http.fetch_html(url) if not self.uses_js else self.fetch_js(url)

    # -- main loop -------------------------------------------------------
    def run(self):
        t0 = time.monotonic()
        retailer_id = dbapi.get_retailer_id(self.slug)
        if retailer_id is None:
            raise RuntimeError(f"Retailer slug not found in DB: {self.slug} (run app.seed first)")

        # Resume support: skip product URLs already scraped.
        #   SCRAPER_SKIP_EXISTING=1  -> skip ALL URLs already in the DB for
        #                               this retailer (robust restart mode)
        #   SCRAPER_SKIP_RECENT=<s>  -> skip URLs scraped within the last s seconds
        import os

        skip_existing = os.environ.get("SCRAPER_SKIP_EXISTING", "0") == "1"
        skip_recent_s = int(os.environ.get("SCRAPER_SKIP_RECENT", "0"))
        self._recent_urls: set[str] = set()
        if (skip_existing or skip_recent_s > 0) and not self.dry_run:
            from sqlalchemy import select as _select

            from ..shared.db import Product as _Product, SessionLocal as _SL

            db0 = _SL()
            try:
                q = _select(_Product.retailer_url).where(_Product.retailer_id == retailer_id)
                if not skip_existing:
                    from datetime import datetime, timedelta, timezone

                    cutoff = datetime.now(timezone.utc) - timedelta(seconds=skip_recent_s)
                    q = q.where(_Product.last_scraped_at > cutoff)
                rows = db0.execute(q).scalars()
                self._recent_urls = {u.rstrip("/") for u in rows if u}
            finally:
                db0.close()
            log.info(
                "[%s] skipping %d already-scraped URLs (mode=%s)",
                self.slug, len(self._recent_urls), "existing" if skip_existing else "recent",
            )

        job_id = None if self.dry_run else dbapi.start_scrape_job(retailer_id)
        db = dbapi.SessionLocal() if not self.dry_run else None
        _since_commit = 0
        try:
            for cat_key, cat_url in self._iter_categories():
                if self.limit and self.stats["found"] >= self.limit:
                    break
                log.info("[%s] crawling category: %s", self.slug, cat_url)
                html = self.fetch(cat_url)
                if not html:
                    self.errors.append(f"category fetch failed: {cat_url}")
                    continue
                # Category-page-direct entries (brochure directories etc.)
                inline = self.extract_from_category(html, cat_url)
                if inline is not None:
                    _inline_since_commit = 0
                    for product in inline:
                        if self.limit and self.stats["found"] >= self.limit:
                            break
                        self.stats["found"] += 1
                        try:
                            self._persist(product, cat_key, db, retailer_id)
                        except Exception as e:
                            log.exception("[%s] error persisting inline %s", self.slug, product.get("name"))
                            self.errors.append(f"inline {product.get('name')}: {e}")
                            self.stats["failed"] += 1
                        if db:
                            _inline_since_commit += 1
                            if _inline_since_commit >= 25:
                                db.commit()
                                _inline_since_commit = 0
                    if db:
                        db.commit()
                    continue
                for prod_url in self.list_product_urls(html, cat_url):
                    if self.limit and self.stats["found"] >= self.limit:
                        break
                    self._process_product(prod_url, cat_key, db, retailer_id)
                    # commit periodically so a crash doesn't lose the whole run
                    if db:
                        _since_commit += 1
                        if _since_commit >= 10:
                            db.commit()
                            _since_commit = 0
            if db:
                db.commit()
        finally:
            if db:
                db.close()
            self.http.close()
            if job_id:
                dbapi.finish_scrape_job(
                    job_id,
                    self.stats["found"],
                    self.stats["new"],
                    self.stats["updated"],
                    self.stats["failed"],
                    self.errors,
                    int(time.monotonic() - t0),
                )
        return self.stats

    def _iter_categories(self):
        for cat_key, cat_url in self.start_categories:
            if self.categories and cat_key not in self.categories:
                continue
            yield cat_key, self.abs_url(cat_url)

    def _process_product(self, prod_url: str, cat_key: str, db, retailer_id: int):
        url = self.abs_url(prod_url)
        if getattr(self, "_recent_urls", None) and url.rstrip("/") in self._recent_urls:
            self.stats["skipped"] += 1
            return
        if self.limit and self.stats["found"] >= self.limit:
            return
        self.stats["found"] += 1
        try:
            html = self.fetch(url)
            if not html:
                self.errors.append(f"product fetch failed: {url}")
                self.stats["failed"] += 1
                return
            product = self.extract_product(html, url)
            if not product:
                self.stats["failed"] += 1
                return
            self._persist(product, cat_key, db, retailer_id)
        except Exception as e:
            log.exception("[%s] error on %s", self.slug, url)
            self.errors.append(f"{url}: {e}")
            self.stats["failed"] += 1

    def _persist(self, product: dict, cat_key: str, db, retailer_id: int):
        # product-level category_key wins (sitemap-driven vendors attribute
        # per-product); fall back to the category loop's key.
        category_slug, cat_name = self.map_category(product.get("category_key") or cat_key)
        cat_id = None
        if not self.dry_run:
            cat_id = dbapi.get_or_create_category(db, category_slug, cat_name)

        sku = product["retailer_sku"]
        images = []
        for i, img_url in enumerate(product.get("image_urls", [])[:8]):
            main_url, thumb_url = img_url, None
            if not self.dry_run:
                if str(img_url).startswith("file://"):
                    # local source file (e.g. brochure PDF crop): process it
                    # through the same pipeline instead of downloading.
                    from pathlib import Path

                    local = Path(img_url[len("file://"):])
                    if local.exists():
                        data = local.read_bytes()
                        from ..shared import images as images_mod

                        try:
                            webp, thumb = images_mod._process(data)
                            key_dir = f"{self.slug}/{sku}"
                            out_dir = config.PRODUCT_IMAGE_DIR / key_dir
                            out_dir.mkdir(parents=True, exist_ok=True)
                            (out_dir / f"img_{i:02d}.webp").write_bytes(webp)
                            (out_dir / f"img_{i:02d}_thumb.webp").write_bytes(thumb)
                            main_url = f"/products/{key_dir}/img_{i:02d}.webp"
                            thumb_url = f"/products/{key_dir}/img_{i:02d}_thumb.webp"
                        except Exception as e:
                            log.warning("  local image processing failed %s: %s", local, e)
                            main_url, thumb_url = None, None
                    else:
                        main_url, thumb_url = None, None
                else:
                    main_url, thumb_url = store_image(
                        self.http.fetch_bytes, self.abs_url(img_url), self.slug, sku, i
                    )
            if main_url is None and str(img_url).startswith("file://"):
                continue  # local source failed to process — no URL to serve
            images.append(
                {
                    "image_url": main_url or img_url,
                    "thumb_url": thumb_url,
                    "original_url": img_url if str(img_url).startswith("file://") else self.abs_url(img_url),
                    "alt_text": product.get("name"),
                    "is_primary": i == 0,
                }
            )

        row = dict(product)
        row["retailer_url"] = self.abs_url(product.get("retailer_url") or "")
        row["category"] = category_slug
        row["category_id"] = cat_id
        row["main_image_url"] = images[0]["image_url"] if images else None
        row["thumbnail_url"] = (images[0]["thumb_url"] or images[0]["image_url"]) if images else None

        if self.dry_run:
            self.stats["new"] += 1
            log.info(
                "  [dry-run] %s | £%s | %s | %s",
                product["name"], product.get("price_gbp"), category_slug, row["retailer_url"],
            )
            return

        result = dbapi.upsert_product(db, row, retailer_id)
        if result["new"]:
            self.stats["new"] += 1
        elif result["changed"]:
            self.stats["updated"] += 1
        else:
            self.stats["skipped"] += 1
        dbapi.replace_images(db, result["id"], images)
        log.info(
            "  %s %s | £%s | %s",
            "NEW" if result["new"] else "UPD" if result["changed"] else "same",
            product["name"][:60], product.get("price_gbp"), category_slug,
        )
