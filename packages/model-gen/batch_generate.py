"""DB-driven batch 3D model generation (doc 03 §2.5 / Phase 5.4).

Runs OUTSIDE Blender (in the apps/api venv). It:
  1. queries products needing models (model_status='pending' or needs_model_update)
  2. maps category -> generator slug
  3. writes a product JSON spec and invokes Blender headless per product:
       blender.exe --background --python gen_one.py -- <spec.json>
  4. on success updates products (model_url, model_status, file size, polys,
     thumbnail, method) and writes a ModelJob row.

Run:
  python batch_generate.py                        # all pending
  python batch_generate.py --retailer ideal-bathrooms
  python batch_generate.py --category toilets
  python batch_generate.py --product-id 1234
  python batch_generate.py --dry-run              # list what would run
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "apps" / "api"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import ModelJob, Product  # noqa: E402

BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
GEN_ONE = Path(__file__).resolve().parent / "gen_one.py"
ROOT = Path(__file__).resolve().parent.parent.parent

# Normalized category prefix -> blender_lib builder slug.
CATEGORY_TO_SLUG = {
    "toilets": "toilet",
    "basins": "basin",
    "baths": "bath",
    "showering/shower-trays": "shower-tray",
    "showering/shower-screens": "shower-screen",
    # wall/ceiling panels + flooring = flat boards
    "tiles-panels/shower-wall-panels": "panel",
    "tiles-panels/ceiling-panels": "panel",
    "tiles-panels/floor-tiles": "panel",
    # brochure enclosures (glass corner units, e.g. Nuie lucie/rene ranges)
    # get the dedicated enclosure builder (wall panels + front door + rails)
    "showering/shower-enclosures": "shower-enclosure",
    "showering/shower-heads": "shower-head",
    "showering/shower-handsets": "shower-head",
    "showering/shower-sets": "shower-set",
    "heating/radiators": "radiator",
    "heating/towel-rails": "towel-rail",
    "mirrors-cabinets/mirrors": "mirror",
    "mirrors-cabinets/illuminated-mirrors": "mirror",
    "mirrors-cabinets/mirror-cabinets": "cabinet",
    # plain 'mirrors-cabinets' (Tissino sitemap) -> cabinet builder
    "mirrors-cabinets": "cabinet",
    "furniture/vanity-units": "vanity-unit",
    # plain 'furniture' (Q4 brochure) -> vanity-unit builder
    "furniture": "vanity-unit",
    # plain 'showering' (Q4 shower kits/valves) -> shower-set builder
    "showering": "shower-set",
    # fitted/wall-mounted/floorstanding/cloakroom/BTW furniture all get the
    # vanity-unit builder (box + basin) scaled to real dims
    "furniture/fitted": "vanity-unit",
    "furniture/wall-mounted": "vanity-unit",
    "furniture/floorstanding": "vanity-unit",
    "furniture/cloakroom-units": "vanity-unit",
    "furniture/btw-units": "vanity-unit",
    "furniture/with-basins": "vanity-unit",
    "furniture/with-worktops": "vanity-unit",
    "furniture/handles": "vanity-unit",
    # toilet + basin combo units model as a toilet
    "ideal-bathrooms/combined-units": "toilet",
    "taps": "tap",
    "accessories/shelves": "shelf",
    # plain 'accessories' (Q4 brochure misc) -> shelf builder as generic small item
    "accessories": "shelf",
    "accessories/towel-rings": "towel-ring",
    "accessories/robe-hooks": "robe-hook",
    "accessories/soap-dishes": "soap-dish",
}


def get_pending(filters: dict):
    db = SessionLocal()
    try:
        q = select(Product).where(
            Product.model_status == "pending",
            Product.category.isnot(None),
        )
        if filters.get("product_id"):
            q = select(Product).where(Product.id == filters["product_id"])
        if filters.get("retailer"):
            from app.models import Retailer

            q = q.join(Retailer).where(Retailer.slug == filters["retailer"])
        if filters.get("brand"):
            q = q.where(Product.brand == filters["brand"])
        if filters.get("category"):
            q = q.where(Product.category.like(f"{filters['category']}%"))
        return db.scalars(q.limit(2000)).all()
    finally:
        db.close()


def slug_for_category(category: str) -> str | None:
    """Map a product category to a builder slug. Longest prefix wins so a
    plain parent key ('accessories') never shadows 'accessories/towel-rings'."""
    best, best_len = None, 0
    for prefix, slug in CATEGORY_TO_SLUG.items():
        if category.startswith(prefix) and len(prefix) > best_len:
            best, best_len = slug, len(prefix)
    return best


def generate_one(product) -> dict:
    """Run Blender headless for one product. Returns {ok, glb_path, polys, error}."""
    slug = slug_for_category(product.category)
    if not slug:
        return {"ok": False, "error": f"no generator for category {product.category}"}

    spec = {
        "id": product.id,
        "slug": slug,
        "width_mm": float(product.width_mm) if product.width_mm else None,
        "height_mm": float(product.height_mm) if product.height_mm else None,
        "depth_mm": float(product.depth_mm) if product.depth_mm else None,
        "finish": (product.finishes or ["chrome"])[0] if product.finishes else "chrome",
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(spec, f)
        spec_path = f.name

    cmd = [BLENDER, "--background", "--python", str(GEN_ONE), "--", spec_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = proc.stdout + proc.stderr
        if "MODEL_OK" in out:
            import re

            m = re.search(r"MODEL_OK\s+\d+\s+glb=(\S+)\s+polys=(\d+)", out)
            polys = int(m.group(2)) if m else 0
            return {"ok": True, "glb_path": m.group(1) if m else None, "polys": polys, "error": None}
        # extract the failure line
        fail = [l for l in out.splitlines() if "FAIL" in l or "Error" in l or "Traceback" in l]
        return {"ok": False, "error": (fail[-1] if fail else out[-400:])}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Blender timed out"}
    finally:
        try:
            Path(spec_path).unlink()
        except OSError:
            pass


def record(db, product_id, result):
    # Re-fetch the product in THIS session — the object passed from get_pending
    # belongs to a closed session and mutations there are silently dropped.
    product = db.get(Product, product_id)
    if result["ok"]:
        out_stem = f"model_{product_id}"
        glb = ROOT / "assets" / "models" / f"{out_stem}.glb"
        size_kb = glb.stat().st_size // 1024 if glb.exists() else None
        product.model_url = f"/models/{out_stem}.glb"
        # keep an existing product-photo thumbnail (brochure scrapes) — the
        # photo is a better catalogue card image than the parametric render
        if not product.thumbnail_url:
            product.thumbnail_url = f"/thumbnails/{out_stem}.png"
        product.model_status = "ready"
        product.model_method = "parametric"
        product.model_polygons = result.get("polys")
        product.model_file_kb = size_kb
        product.needs_model_update = False
        job = ModelJob(
            product_id=product_id,
            method="parametric",
            status="completed",
            output_url=product.model_url,
            thumbnail_url=product.thumbnail_url,
            polygon_count=result.get("polys"),
            file_size_kb=size_kb,
            completed_at=datetime.now(timezone.utc),
        )
    else:
        product.model_status = "failed"
        job = ModelJob(
            product_id=product_id,
            method="parametric",
            status="failed",
            error_message=result["error"],
            completed_at=datetime.now(timezone.utc),
        )
    db.add(job)


def main():
    p = argparse.ArgumentParser(description="Batch generate 3D models (doc 03 §2.5)")
    p.add_argument("--retailer", help="Retailer slug")
    p.add_argument("--brand", help="Exact brand name (e.g. 'Nuie Bathrooms')")
    p.add_argument("--category", help="Category prefix")
    p.add_argument("--product-id", type=int, help="Single product id")
    p.add_argument("--dry-run", action="store_true", help="List what would run")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    filters = {k: v for k, v in vars(args).items() if v and k not in ("dry_run", "limit")}
    products = get_pending(filters)
    if args.limit:
        products = products[: args.limit]

    # map to slugs + drop unsupported categories
    runnable = []
    for pr in products:
        slug = slug_for_category(pr.category)
        if slug:
            runnable.append((pr, slug))
    print(f"Found {len(products)} pending; {len(runnable)} have a generator slot.")

    if args.dry_run:
        for pr, slug in runnable:
            print(f"  [{pr.id}] {pr.name} -> {slug} ({pr.width_mm}x{pr.height_mm}x{pr.depth_mm}mm)")
        return

    db = SessionLocal()
    ok = failed = 0
    try:
        for pr, slug in runnable:
            print(f"\n[{pr.id}] {pr.name} -> {slug}", flush=True)
            result = generate_one(pr)
            if result["ok"]:
                ok += 1
                print(f"  ✓ model_{pr.id}.glb ({result['polys']} polys)")
            else:
                failed += 1
                print(f"  ✗ {result['error']}")
            record(db, pr.id, result)
        db.commit()
    finally:
        db.close()
    print(f"\nDone: {ok} generated, {failed} failed.")


if __name__ == "__main__":
    main()