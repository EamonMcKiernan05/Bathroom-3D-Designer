"""Shared DB pipeline (doc 02 §1 step 4-5): upsert products + images,
get-or-create categories, track scrape_jobs, flag model regeneration.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import select

from .. import config

# The scraper package shares the API's models/db — single schema source of truth.
sys.path.insert(0, str(config.API_DIR))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    Product,
    ProductImage,
    Retailer,
    ScrapeJob,
)

log = logging.getLogger("scraper.db")

_categories_cache: dict[str, int] = {}


def get_retailer_id(slug: str) -> int:
    db = SessionLocal()
    try:
        r = db.scalar(select(Retailer).where(Retailer.slug == slug))
        return r.id if r else None
    finally:
        db.close()


def _load_categories(db) -> dict[str, int]:
    return {c.slug: c.id for c in db.scalars(select(Category)).all()}


def get_or_create_category(db, slug: str, name: str | None = None) -> int:
    """Normalized category slug → id, creating a leaf row when unknown.

    doc 02 §6.4: categories split by vendor when no normalized mapping exists —
    fallback slugs live under the vendor root (e.g. 'ideal-bathrooms/toilet-seats').
    """
    global _categories_cache
    if not _categories_cache:
        _categories_cache = _load_categories(db)
    if slug in _categories_cache:
        return _categories_cache[slug]

    parent_slug = None
    if "/" in slug:
        parent_slug = slug.rsplit("/", 1)[0]
    depth = slug.count("/")
    parent_id = None
    if parent_slug and parent_slug in _categories_cache:
        parent_id = _categories_cache[parent_slug]
    elif parent_slug:
        parent_id = get_or_create_category(db, parent_slug)

    cat = Category(slug=slug, name=name or slug.replace("/", " / ").title(), depth=depth, parent_id=parent_id)
    db.add(cat)
    db.flush()
    _categories_cache[slug] = cat.id
    return cat.id


def upsert_product(db, product: dict, retailer_id: int) -> dict:
    """Insert or update one product keyed on (retailer_id, retailer_sku).

    Returns {'new': bool, 'changed': bool, 'id': int}.
    Mirrors doc 02 §3.4 upsert: price/images/dims/finishes refreshed,
    needs_model_update flagged when dimensions change.
    """
    sku = product["retailer_sku"]
    existing = db.scalar(
        select(Product).where(Product.retailer_id == retailer_id, Product.retailer_sku == sku)
    )
    now = datetime.now(timezone.utc)

    dims_changed = False
    if existing:
        for col in ("width_mm", "height_mm", "depth_mm", "diameter_mm"):
            if (getattr(existing, col) or None) != (product.get(col) or None):
                dims_changed = True

    fields = dict(
        name=product["name"],
        brand=product.get("brand"),
        category_id=product.get("category_id"),
        category=product.get("category"),
        description=product.get("description"),
        price_gbp=product.get("price_gbp"),
        price_note=product.get("price_note"),
        price_is_from=product.get("price_is_from", False),
        width_mm=product.get("width_mm"),
        height_mm=product.get("height_mm"),
        depth_mm=product.get("depth_mm"),
        diameter_mm=product.get("diameter_mm"),
        dimensions_confidence=product.get("dimensions_confidence"),
        finishes=product.get("finishes") or [],
        colours=product.get("colours") or [],
        sizes=product.get("sizes") or [],
        variant_data=product.get("variant_data") or {},
        retailer_url=product.get("retailer_url"),
        main_image_url=product.get("main_image_url"),
        thumbnail_url=product.get("thumbnail_url"),
        in_stock=product.get("in_stock"),
        active=True,
        last_scraped_at=now,
    )
    # Optional pass-through: vendors that know a product needs no model
    # (e.g. brochure entries) can set it explicitly. Normal scrapes omit the
    # key so existing model_status is never clobbered.
    if product.get("model_status"):
        fields["model_status"] = product["model_status"]

    if existing is None:
        fields.update(first_scraped_at=now, created_at=now, updated_at=now)
        p = Product(retailer_id=retailer_id, retailer_sku=sku, **fields)
        db.add(p)
        db.flush()
        return {"new": True, "changed": True, "id": p.id}

    # update + dimension-change detection for model regeneration (doc 02 §3.4)
    changed = False
    for k, v in fields.items():
        if getattr(existing, k) != v:
            changed = True
            setattr(existing, k, v)
    if dims_changed:
        existing.needs_model_update = True
        existing.model_status = "pending"
        changed = True
    existing.updated_at = now
    db.flush()
    return {"new": False, "changed": changed, "id": existing.id}


def replace_images(db, product_id: int, images: list[dict]):
    """Replace a product's image rows (image_url NOT NULL, original_url, alt_text, is_primary)."""
    existing = list(db.scalars(select(ProductImage).where(ProductImage.product_id == product_id)))
    seen = {im["image_url"] for im in images}
    for row in existing:
        if row.image_url not in seen:
            db.delete(row)
    for i, im in enumerate(images):
        url = im["image_url"]
        row = next((r for r in existing if r.image_url == url), None)
        if row is None:
            row = ProductImage(product_id=product_id)
            db.add(row)
        row.image_url = url  # NOT NULL — must always be set
        row.original_url = im.get("original_url")
        row.alt_text = im.get("alt_text")
        row.sort_order = i
        row.is_primary = i == 0
    db.flush()


def start_scrape_job(retailer_id: int, job_type: str = "full") -> int:
    db = SessionLocal()
    try:
        job = ScrapeJob(retailer_id=retailer_id, job_type=job_type, status="running")
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


def finish_scrape_job(
    job_id: int,
    found: int,
    new: int,
    updated: int,
    failed: int,
    errors: list[str],
    duration_secs: int,
):
    db = SessionLocal()
    try:
        job = db.get(ScrapeJob, job_id)
        if not job:
            return
        job.status = "completed" if failed == 0 else "failed"
        job.products_found = found
        job.products_new = new
        job.products_updated = updated
        job.products_failed = failed
        job.errors = errors[:50]
        job.completed_at = datetime.now(timezone.utc)
        job.duration_secs = duration_secs
        db.commit()
    finally:
        db.close()


def ensure_schema():
    Base.metadata.create_all(engine)
