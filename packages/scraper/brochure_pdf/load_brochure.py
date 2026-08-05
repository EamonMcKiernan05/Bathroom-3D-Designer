"""Load parsed brochure rows (parse_nuie.py output) into the catalogue.

Each variant SKU becomes one product under the retailer that stocks the
brochure (ideal-bathrooms), with `brand` set to the brochure's manufacturer
so the catalogue shows the real supplier (Nuie, Armitage Shanks, ...).

    python -m scraper.brochure_pdf.load_brochure \
        --rows assets/brochures/nuie-bathrooms/nuie_rows.json \
        --brand "Nuie Bathrooms" \
        --retailer ideal-bathrooms \
        [--dry-run] [--limit N]

Run with the apps/api venv python from packages/.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scraper import config  # noqa: E402
from scraper.shared import db as dbapi  # noqa: E402
from scraper.shared import images as images_mod  # noqa: E402

log = logging.getLogger("scraper.brochure")

RETAILER_NAME = {
    "Nuie Bathrooms": "Nuie Bathrooms",
}

# Hidden plumbing + small parts are out of scope for the 3D catalogue
# (user decision 2026-08-05): bath/basin wastes, overflows, traps, pipes,
# drains, taps/mixers, shower shelves. They stay generic.
EXCLUDE_RE = re.compile(
    r"\bwastes?\b|\boverflows?\b|\btraps?\b|\bpipework?\b|\bdrains?\b|"
    r"\btaps?\b|\bmixer\b|\bshelf\b|\bshelving\b|\bleg set\b|\bfixing\b",
    re.I,
)


def is_excluded(v: dict) -> bool:
    hay = " ".join(
        str(x) for x in (v.get("name"), v.get("row_desc"), v.get("category")) if x
    )
    return bool(EXCLUDE_RE.search(hay))


def clean_name(name: str, variant_sku: str) -> str:
    name = " ".join(name.split())
    return name


def build_row(v: dict, brand: str, retailer_slug: str) -> dict:
    dims = dict(v.get("dims", {}))
    # Nuie enclosures are 1900mm tall even when the page-level feature
    # height didn't propagate (page 72/76 rows with height None)
    if dims.get("height_mm") is None and (v.get("category") or "").startswith("showering"):
        dims["height_mm"] = 1900
    sku = v["sku"]
    imgs = []
    if v.get("image"):
        imgs.append("file://" + str(EXTRACT_DIR / v["image"]))
    name = clean_name(v["name"], sku)
    if v.get("hand"):
        name += f" ({v['hand']})"
    size_tag = v.get("size_raw", "").split("mm")[0].strip()
    # avoid '... 50x60cmmm' when the size string already carries a unit
    if size_tag and not size_tag.lower().endswith(("cm", '"', "'")):
        display_size = f"{size_tag}mm"
    else:
        display_size = size_tag
    return {
        # SKU namespaced by brand prefix so codes can't collide across brands
        "retailer_sku": f"{BRAND_SLUG}-{sku}",
        "retailer_url": BROCHURE_SOURCE_URL,
        "name": f"{name} {display_size}".strip(),
        "brand": brand,
        "description": (
            f"{brand} — {name}. Brochure spec: {v.get('size_raw','').strip()}, "
            f"code {sku}. Sourced from the {brand} brochure stocked by "
            f"Ideal Bathrooms Isle of Man."
        ),
        "price_gbp": v.get("price_gbp"),
        "price_note": "inc VAT",
        "price_is_from": False,
        "width_mm": dims.get("width_mm"),
        "height_mm": dims.get("height_mm"),
        "depth_mm": dims.get("depth_mm"),
        "diameter_mm": dims.get("diameter_mm"),
        "dimensions_confidence": "high" if dims.get("width_mm") else None,
        "finishes": [],
        "colours": [],
        "sizes": [v.get("size_raw", "").strip()] if v.get("size_raw") else [],
        "variant_data": {"hand": v.get("hand"), "internal_depth_mm": dims.get("internal_depth_mm")},
        "image_urls": imgs,
        "in_stock": None,
        "category_key": v.get("category"),
        # brochure items without a parametric builder stay pending; the model
        # generator picks them up by category
    }


def store_local_image(img_url: str, slug: str, sku: str, index: int):
    local = Path(img_url[len("file://"):])
    if not local.exists():
        return None, None
    try:
        webp, thumb = images_mod._process(local.read_bytes())
    except Exception as e:
        log.warning("image process failed %s: %s", local, e)
        return None, None
    key_dir = f"{slug}/{sku}"
    out_dir = config.PRODUCT_IMAGE_DIR / key_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"img_{index:02d}.webp").write_bytes(webp)
    (out_dir / f"img_{index:02d}_thumb.webp").write_bytes(thumb)
    return f"/products/{key_dir}/img_{index:02d}.webp", f"/products/{key_dir}/img_{index:02d}_thumb.webp"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--brand", required=True)
    ap.add_argument("--retailer", default="ideal-bathrooms")
    ap.add_argument("--source-url", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s")

    global EXTRACT_DIR, BROCHURE_SOURCE_URL, BRAND_SLUG
    EXTRACT_DIR = Path(args.rows).parent / "extracted"
    BROCHURE_SOURCE_URL = args.source_url or f"https://idealbathrooms.im/prod_cat/C_brochures-_55.shtml"
    BRAND_SLUG = "".join(c if c.isalnum() else "-" for c in args.brand.lower()).strip("-")

    rows = json.loads(Path(args.rows).read_text(encoding="utf-8"))
    # drop hidden plumbing + small parts (wastes/overflows/taps/...)
    before = len(rows)
    rows = [v for v in rows if not is_excluded(v)]
    log.info("excluded %d small/hidden-part rows", before - len(rows))
    # dedupe: the same SKU can appear in multiple spec tables on one page
    seen, deduped = set(), []
    for v in rows:
        if v["sku"] in seen:
            continue
        seen.add(v["sku"])
        deduped.append(v)
    rows = deduped
    if args.limit:
        rows = rows[: args.limit]
    log.info("loading %d variants for %s -> retailer %s", len(rows), args.brand, args.retailer)

    retailer_id = dbapi.get_retailer_id(args.retailer)
    if retailer_id is None:
        log.error("retailer %s not in DB", args.retailer)
        sys.exit(1)

    if not args.dry_run:
        dbapi.ensure_schema()
    db = None if args.dry_run else dbapi.SessionLocal()

    stats = {"new": 0, "updated": 0, "same": 0, "failed": 0}
    t0 = time.monotonic()
    try:
        for i, v in enumerate(rows):
            try:
                row = build_row(v, args.brand, args.retailer)
                category_slug = row["category_key"] or "uncategorised"
                cat_id = None
                if not args.dry_run:
                    cat_id = dbapi.get_or_create_category(db, category_slug, None)
                # images
                images = []
                for j, img_url in enumerate(row["image_urls"][:4]):
                    main_url, thumb_url = img_url, None
                    if not args.dry_run:
                        main_url, thumb_url = store_local_image(img_url, args.retailer, row["retailer_sku"], j)
                    images.append({
                        "image_url": main_url or img_url,
                        "thumb_url": thumb_url,
                        "original_url": img_url,
                        "alt_text": row["name"],
                        "is_primary": j == 0,
                    })
                data = dict(row)
                data["category"] = category_slug
                data["category_id"] = cat_id
                data["main_image_url"] = images[0]["image_url"] if images else None
                data["thumbnail_url"] = (images[0]["thumb_url"] or images[0]["image_url"]) if images else None
                if args.dry_run:
                    stats["new"] += 1
                    log.info("  [dry] %s | £%s | %s", row["name"][:55], row["price_gbp"], category_slug)
                    continue
                res = dbapi.upsert_product(db, data, retailer_id)
                stats["new" if res["new"] else ("updated" if res["changed"] else "same")] += 1
                dbapi.replace_images(db, res["id"], images)
                if (i + 1) % 10 == 0:
                    db.commit()
                    log.info("  ...%d/%d", i + 1, len(rows))
            except Exception as e:
                log.exception("variant %s failed", v.get("sku"))
                stats["failed"] += 1
        if db:
            db.commit()
    finally:
        if db:
            db.close()
    log.info("done in %ds: %s", int(time.monotonic() - t0), stats)


EXTRACT_DIR = None
BROCHURE_SOURCE_URL = None
BRAND_SLUG = None

if __name__ == "__main__":
    main()
