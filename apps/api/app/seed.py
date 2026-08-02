"""Seed the database: retailers, categories, demo products, textures.

Run:  python -m app.seed   (from apps/api, after venv activate)
Tolerant: products whose GLB model file doesn't exist yet get model_status='pending'.
"""
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import (
    Category,
    Product,
    Retailer,
    Texture,
    TextureMap,
)

ROOT = Path(__file__).resolve().parent.parent.parent.parent
ASSETS = ROOT / "assets"

RETAILERS = [
    {"slug": "crosswater", "name": "Crosswater", "website_url": "https://www.crosswater.co.uk/", "country": "UK"},
    {"slug": "mylife", "name": "MyLife Bathrooms", "website_url": "https://mylifebathrooms.com/", "country": "UK"},
    {"slug": "city-plumbing", "name": "City Plumbing", "website_url": "https://www.cityplumbing.co.uk/", "country": "UK"},
    {"slug": "genesis", "name": "Genesis Global Systems", "website_url": "https://www.genesis-gs.com/", "country": "UK"},
    {"slug": "warren-keys", "name": "Warren Keys Isle of Man", "website_url": "https://wkbom.im/", "country": "IOM"},
    {"slug": "ideal-bathrooms", "name": "Ideal Bathrooms IoM", "website_url": "https://idealbathrooms.im/", "country": "IOM"},
]

# (slug, name, depth, parent_slug, icon)
CATEGORIES = [
    ("toilets", "Toilets", 0, None, "toilet"),
    ("toilets/close-coupled", "Close Coupled Toilets", 1, "toilets", "toilet"),
    ("toilets/back-to-wall", "Back To Wall Toilets", 1, "toilets", "toilet"),
    ("toilets/wall-hung", "Wall Hung Toilets", 1, "toilets", "toilet"),
    ("basins", "Basins", 0, None, "basin"),
    ("basins/pedestal", "Pedestal Basins", 1, "basins", "basin"),
    ("basins/wall-hung", "Wall Hung Basins", 1, "basins", "basin"),
    ("basins/countertop", "Countertop Basins", 1, "basins", "basin"),
    ("baths", "Baths", 0, None, "bath"),
    ("baths/single-ended", "Single Ended Baths", 1, "baths", "bath"),
    ("baths/double-ended", "Double Ended Baths", 1, "baths", "bath"),
    ("baths/freestanding", "Freestanding Baths", 1, "baths", "bath"),
    ("baths/shower-bath", "Shower Baths", 1, "baths", "bath"),
    ("showering", "Showering", 0, None, "shower"),
    ("showering/shower-trays", "Shower Trays", 1, "showering", "shower"),
    ("showering/shower-screens", "Shower Screens", 1, "showering", "shower"),
    ("showering/shower-heads", "Shower Heads", 1, "showering", "shower"),
    ("showering/shower-handsets", "Shower Handsets", 1, "showering", "shower"),
    ("showering/shower-sets", "Shower Sets", 1, "showering", "shower"),
    ("taps", "Taps", 0, None, "tap"),
    ("taps/basin-taps", "Basin Taps", 1, "taps", "tap"),
    ("taps/basin-taps/mono", "Mono Basin Mixers", 2, "taps/basin-taps", "tap"),
    ("taps/bath-taps", "Bath Taps", 1, "taps", "tap"),
    ("heating", "Heating", 0, None, "radiator"),
    ("heating/radiators", "Radiators", 1, "heating", "radiator"),
    ("heating/towel-rails", "Heated Towel Rails", 1, "heating", "radiator"),
    ("mirrors-cabinets", "Mirrors & Cabinets", 0, None, "mirror"),
    ("mirrors-cabinets/mirrors", "Mirrors", 1, "mirrors-cabinets", "mirror"),
    ("mirrors-cabinets/mirror-cabinets", "Mirror Cabinets", 1, "mirrors-cabinets", "mirror"),
    ("furniture", "Furniture", 0, None, "vanity"),
    ("furniture/vanity-units", "Vanity Units", 1, "furniture", "vanity"),
    ("accessories", "Accessories", 0, None, "accessory"),
    ("accessories/shelves", "Shelves", 1, "accessories", "accessory"),
    ("accessories/towel-rings", "Towel Rings", 1, "accessories", "accessory"),
    ("accessories/robe-hooks", "Robe Hooks", 1, "accessories", "accessory"),
    ("accessories/soap-dishes", "Soap Dishes", 1, "accessories", "accessory"),
]

# (name, category_slug, retailer_slug, sku, price, w, h, d, finish, model_slug, brand)
PRODUCTS = [
    ("Demo Close Coupled Toilet", "toilets/close-coupled", "ideal-bathrooms", "DEMO-WC-001", 149.99, 360, 780, 660, "white", "toilet", "DemoRange"),
    ("Demo Back To Wall Toilet", "toilets/back-to-wall", "ideal-bathrooms", "DEMO-WC-002", 189.99, 360, 790, 510, "white", "toilet", "DemoRange"),
    ("Demo Pedestal Basin", "basins/pedestal", "ideal-bathrooms", "DEMO-BSN-001", 79.99, 560, 790, 470, "white", "basin", "DemoRange"),
    ("Demo Wall Hung Basin", "basins/wall-hung", "ideal-bathrooms", "DEMO-BSN-002", 89.99, 600, 140, 400, "white", "basin", "DemoRange"),
    ("Demo Single Ended Bath", "baths/single-ended", "ideal-bathrooms", "DEMO-BTH-001", 329.99, 1700, 560, 750, "white", "bath", "DemoRange"),
    ("Demo Double Ended Bath", "baths/double-ended", "ideal-bathrooms", "DEMO-BTH-002", 429.99, 1800, 580, 810, "white", "bath", "DemoRange"),
    ("Demo Freestanding Bath", "baths/freestanding", "ideal-bathrooms", "DEMO-BTH-003", 899.99, 1700, 590, 750, "white", "bath", "DemoRange"),
    ("Demo Rectangular Shower Tray", "showering/shower-trays", "city-plumbing", "DEMO-TRY-001", 89.99, 900, 40, 760, "white", "shower-tray", "DemoRange"),
    ("Demo Quadrant Shower Tray", "showering/shower-trays", "city-plumbing", "DEMO-TRY-002", 129.99, 800, 40, 800, "white", "shower-tray", "DemoRange"),
    ("Demo Pivot Shower Screen", "showering/shower-screens", "city-plumbing", "DEMO-SCR-001", 159.99, 800, 1900, 8, "chrome", "shower-screen", "DemoRange"),
    ("Demo Walk-In Shower Screen", "showering/shower-screens", "city-plumbing", "DEMO-SCR-002", 199.99, 1200, 1900, 8, "chrome", "shower-screen", "DemoRange"),
    ("Demo Fixed Shower Head", "showering/shower-heads", "crosswater", "DEMO-HD-001", 34.99, 200, 120, 200, "chrome", "shower-head", "DemoRange"),
    ("Demo Shower Set (Head+Handset)", "showering/shower-sets", "crosswater", "DEMO-SET-001", 89.99, 300, 600, 200, "chrome", "shower-set", "DemoRange"),
    ("Demo Mono Basin Mixer", "taps/basin-taps/mono", "crosswater", "DEMO-TAP-001", 69.99, 50, 130, 160, "chrome", "tap", "DemoRange"),
    ("Demo Bath Filler", "taps/bath-taps", "crosswater", "DEMO-TAP-002", 119.99, 200, 120, 200, "chrome", "tap", "DemoRange"),
    ("Demo Panel Radiator 600x1200", "heating/radiators", "mylife", "DEMO-RAD-001", 189.99, 1200, 600, 70, "anthracite", "radiator", "DemoRange"),
    ("Demo Heated Towel Rail", "heating/towel-rails", "mylife", "DEMO-TWR-001", 249.99, 500, 1200, 100, "chrome", "towel-rail", "DemoRange"),
    ("Demo Round Mirror 600mm", "mirrors-cabinets/mirrors", "mylife", "DEMO-MIR-001", 49.99, 600, 700, 25, "chrome", "mirror", "DemoRange"),
    ("Demo Mirror Cabinet 600mm", "mirrors-cabinets/mirror-cabinets", "mylife", "DEMO-MCB-001", 129.99, 600, 750, 130, "white", "cabinet", "DemoRange"),
    ("Demo Vanity Unit 600mm", "furniture/vanity-units", "mylife", "DEMO-VNY-001", 259.99, 600, 850, 470, "oak", "vanity-unit", "DemoRange"),
    ("Demo Glass Shelf 600mm", "accessories/shelves", "city-plumbing", "DEMO-SHF-001", 39.99, 600, 15, 120, "chrome", "shelf", "DemoRange"),
    ("Demo Towel Ring", "accessories/towel-rings", "crosswater", "DEMO-TRG-001", 24.99, 165, 60, 165, "chrome", "towel-ring", "DemoRange"),
    ("Demo Robe Hook", "accessories/robe-hooks", "crosswater", "DEMO-RBH-001", 12.99, 40, 60, 55, "chrome", "robe-hook", "DemoRange"),
    ("Demo Soap Dish", "accessories/soap-dishes", "crosswater", "DEMO-SPD-001", 14.99, 120, 30, 80, "chrome", "soap-dish", "DemoRange"),
]

FINISHES = ["chrome", "matt_black", "brushed_brass", "brushed_nickel", "white", "anthracite", "oak"]


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()

    # Retailers
    for r in RETAILERS:
        if not db.scalar(select(Retailer).where(Retailer.slug == r["slug"])):
            db.add(Retailer(**r))
    db.commit()
    retailers = {r.slug: r for r in db.scalars(select(Retailer)).all()}

    # Categories
    cat_ids = {}
    for slug, name, depth, parent_slug, icon in CATEGORIES:
        c = db.scalar(select(Category).where(Category.slug == slug))
        if not c:
            c = Category(slug=slug, name=name, depth=depth, icon=icon, sort_order=0)
            db.add(c)
            db.flush()
        cat_ids[slug] = c.id
    db.commit()
    # fix parents after all inserted
    for slug, name, depth, parent_slug, icon in CATEGORIES:
        c = db.scalar(select(Category).where(Category.slug == slug))
        if parent_slug and c.parent_id is None:
            c.parent_id = cat_ids[parent_slug]
    db.commit()

    # Products (idempotent by retailer+sku)
    for name, cat, rslug, sku, price, w, h, d, finish, model_slug, brand in PRODUCTS:
        exists = db.scalar(
            select(Product).where(Product.retailer_id == retailers[rslug].id, Product.retailer_sku == sku)
        )
        if exists:
            continue
        model_path = ASSETS / "models" / f"{model_slug}.glb"
        has_model = model_path.exists()
        # Back-to-wall toilet has different depth (concealed cistern); quadrant tray is 800x800
        depth_actual = d
        width_actual = w
        if sku == "DEMO-WC-002":
            depth_actual = 510
        if sku == "DEMO-TRY-002":
            depth_actual = 800
        p = Product(
            retailer_id=retailers[rslug].id,
            retailer_sku=sku,
            name=name,
            brand=brand,
            category=cat,
            category_id=cat_ids.get(cat),
            price_gbp=price,
            price_note="Demo price",
            price_is_from=False,
            width_mm=width_actual,
            height_mm=h,
            depth_mm=depth_actual,
            dimensions_confidence="high",
            placeholder_kind="generic_shape",
            finishes=[finish, *[f for f in FINISHES if f != finish][:2]],
            model_url=f"/models/{model_slug}.glb" if has_model else None,
            model_status="ready" if has_model else "pending",
            model_method="parametric" if has_model else None,
            thumbnail_url=f"/thumbnails/{model_slug}.png" if has_model else None,
            main_image_url=f"/thumbnails/{model_slug}.png" if has_model else None,
            active=True,
            in_stock=True,
        )
        db.add(p)
    db.commit()

    # Textures from manifest (written by packages/texture-proc)
    manifest = ROOT / "assets" / "textures" / "manifest.json"
    seeded = 0
    if manifest.exists():
        data = json.loads(manifest.read_text())
        for t in data.get("textures", []):
            exists = db.scalar(select(Texture).where(Texture.slug == t["slug"]))
            if exists:
                continue
            tex = Texture(
                slug=t["slug"],
                name=t["name"],
                category=t["category"],
                tile_width_mm=t["tile_width_mm"],
                tile_height_mm=t["tile_height_mm"],
                thickness_mm=t.get("thickness_mm", 9),
                colour_family=t.get("colour_family"),
                finish=t.get("finish", "matte"),
                material=t.get("material", "ceramic"),
                pattern=t.get("pattern", "plain"),
                source_type=t.get("source_type", "custom"),
                license=t.get("license", "custom"),
                active=True,
            )
            db.add(tex)
            db.flush()
            for map_type, url in t.get("maps", {}).items():
                db.add(
                    TextureMap(
                        texture_id=tex.id,
                        map_type=map_type,
                        file_url=url,
                        format="jpg",
                    )
                )
            seeded += 1
        db.commit()
    else:
        print("No texture manifest found — run packages/texture-proc/generate_tiles.py first.")

    print(f"Seeded. Retailers: {len(retailers)} | Categories: {len(cat_ids)} | Products: {len(PRODUCTS)} | Textures added: {seeded}")
    db.close()


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
