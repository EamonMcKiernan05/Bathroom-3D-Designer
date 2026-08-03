"""Generate a 3D model for a single product (doc 03 §2.5 / Phase 5).

    python single_generate.py --product-id 1234
    python single_generate.py --product-id 1234 --dry-run

Thin wrapper over batch_generate narrowed to one product id.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import batch_generate  # noqa: E402


def main():
    import argparse

    p = argparse.ArgumentParser(description="Generate one product's 3D model")
    p.add_argument("--product-id", type=int, required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    products = batch_generate.get_pending({"product_id": args.product_id})
    if not products:
        print(f"No pending product with id {args.product_id} (or it already has a model).")
        return
    product = products[0]
    slug = batch_generate.slug_for_category(product.category)
    if not slug:
        print(f"No generator for category '{product.category}'.")
        return
    print(f"[{product.id}] {product.name} -> {slug} ({product.width_mm}x{product.height_mm}x{product.depth_mm}mm)")

    if args.dry_run:
        print("Dry run — no model generated.")
        return

    from sqlalchemy import select

    from app.db import SessionLocal

    db = SessionLocal()
    try:
        result = batch_generate.generate_one(product)
        if result["ok"]:
            print(f"  ✓ model_{product.id}.glb ({result['polys']} polys)")
        else:
            print(f"  ✗ {result['error']}")
        batch_generate.record(db, product.id, result)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
