"""Seed the generic model catalogue (82 archetypes from the Eastbrook scope doc)
as products of retailer 'generic-catalogue', pointing at assets/models/<slug>.glb.

Run:  python -m app.seed_catalogue   (from apps/api, venv python)
Idempotent by retailer+sku.
"""
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, engine, Base
from app.models import Category, Product, Retailer

ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODELS = ROOT / "assets" / "models"

RETAILER = {"slug": "generic-catalogue", "name": "Generic Catalogue",
            "website_url": "https://example.com/generic-catalogue", "country": "UK"}

# extra categories beyond app.seed's set, needed by the scope
EXTRA_CATEGORIES = [
    ("baths/back-to-wall", "Back To Wall Baths", 1, "baths"),
    ("baths/corner-baths", "Corner Baths", 1, "baths"),
    ("showering/shower-enclosures", "Shower Enclosures", 1, "showering"),
    ("basins/semi-recessed", "Semi-Recessed Basins", 1, "basins"),
    ("basins/cloakroom", "Cloakroom Basins", 1, "basins"),
    ("toilets/bidets", "Bidets", 1, "toilets"),
    ("tiles-panels", "Wall Panels & Tiles", 0, None),
]

CHROME_SET = ["chrome", "matt_black", "brushed_brass", "brushed_nickel"]
WHITE_SET = ["white"]
OAK_SET = ["oak", "white", "matt_black"]

# (slug, name, category, w_mm, h_mm, d_mm, finishes)
CATALOG = [
    # --- baths (18) ---
    ("bath-se-rect-rect", "Single Ended Bath — Rectangular Opening", "baths/single-ended", 1700, 560, 750, WHITE_SET),
    ("bath-se-rect-round", "Single Ended Bath — Round Opening", "baths/single-ended", 1700, 560, 750, WHITE_SET),
    ("bath-se-asym", "Single Ended Bath — Asymmetric Opening", "baths/single-ended", 1700, 560, 750, WHITE_SET),
    ("bath-de-rect-rect", "Double Ended Bath — Rectangular Opening", "baths/double-ended", 1800, 580, 800, WHITE_SET),
    ("bath-de-rect-round", "Double Ended Bath — Round Opening", "baths/double-ended", 1800, 580, 800, WHITE_SET),
    ("bath-btw-dshape", "Back To Wall Bath — D Shape", "baths/back-to-wall", 1700, 560, 750, WHITE_SET),
    ("bath-btw-left", "Back To Wall Bath — Left Hand Offset", "baths/back-to-wall", 1700, 560, 750, WHITE_SET),
    ("bath-btw-right", "Back To Wall Bath — Right Hand Offset", "baths/back-to-wall", 1700, 560, 750, WHITE_SET),
    ("bath-btw-caversham", "Back To Wall Bath — Ridged Panel", "baths/back-to-wall", 1700, 560, 750, WHITE_SET),
    ("bath-corner-generic", "Corner Bath — Angled Front", "baths/corner-baths", 1400, 560, 1400, WHITE_SET),
    ("bath-corner-whitchurch", "Corner Bath — Curved Front", "baths/corner-baths", 1450, 560, 1450, WHITE_SET),
    ("bath-fs-plinth", "Freestanding Bath — Plinth Base", "baths/freestanding", 1700, 580, 750, WHITE_SET),
    ("bath-fs-feet", "Freestanding Bath — Feet", "baths/freestanding", 1700, 580, 750, WHITE_SET),
    ("bath-fs-slipper", "Freestanding Bath — Slipper", "baths/freestanding", 1700, 620, 750, WHITE_SET),
    ("bath-fs-round", "Freestanding Bath — Round", "baths/freestanding", 1500, 580, 1500, WHITE_SET),
    ("bath-fs-boat", "Freestanding Bath — Boat Shape", "baths/freestanding", 1800, 600, 800, WHITE_SET),
    ("bath-p-shape", "P-Shape Shower Bath", "baths/shower-bath", 1700, 560, 750, WHITE_SET),
    ("bath-l-shape", "L-Shape Shower Bath", "baths/shower-bath", 1700, 560, 750, WHITE_SET),
    # --- screens (6) ---
    ("screen-static-square", "Static Shower Screen — Square Corner", "showering/shower-screens", 800, 1900, 8, CHROME_SET),
    ("screen-static-rounded", "Static Shower Screen — Rounded Corner", "showering/shower-screens", 800, 1900, 8, CHROME_SET),
    ("screen-hinged", "Hinged Folding Bath Screen", "showering/shower-screens", 1200, 1900, 8, CHROME_SET),
    ("screen-curved", "Curved Bath Screen", "showering/shower-screens", 1400, 1500, 8, CHROME_SET),
    ("screen-sliding-straight", "Sliding Shower Screen — Straight", "showering/shower-screens", 1200, 1900, 8, CHROME_SET),
    ("screen-sliding-curved", "Sliding Shower Screen — Curved", "showering/shower-screens", 1400, 1500, 8, CHROME_SET),
    # --- enclosures (14) ---
    ("enc-corner-sq-sliding", "Corner Enclosure — Sliding Door", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-corner-sq-dsliding", "Corner Enclosure — Double Sliding Door", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-corner-sq-bifold", "Corner Enclosure — Bi-Fold Door", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-corner-sq-open", "Corner Enclosure — Open", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-corner-sq-panel", "Corner Enclosure — Single Fixed Panel", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-quadrant-sliding", "Quadrant Enclosure — Sliding Door", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-quadrant-bifold", "Quadrant Enclosure — Bi-Fold Door", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-quadrant-open", "Quadrant Enclosure — Open", "showering/shower-enclosures", 900, 1900, 900, CHROME_SET),
    ("enc-midwall-sliding", "Mid-Wall Enclosure — Sliding Door", "showering/shower-enclosures", 1200, 1900, 900, CHROME_SET),
    ("enc-midwall-dbifold", "Mid-Wall Enclosure — Double Bi-Fold Door", "showering/shower-enclosures", 1200, 1900, 900, CHROME_SET),
    ("enc-midwall-open", "Mid-Wall Enclosure — Open", "showering/shower-enclosures", 1200, 1900, 900, CHROME_SET),
    ("enc-dooronly-sliding", "Door Only — Sliding", "showering/shower-enclosures", 900, 1900, 50, CHROME_SET),
    ("enc-dooronly-bifold", "Door Only — Bi-Fold", "showering/shower-enclosures", 900, 1900, 50, CHROME_SET),
    ("enc-dooronly-gap", "Door Only — Gap Frame", "showering/shower-enclosures", 900, 1900, 50, CHROME_SET),
    # --- trays (3) ---
    ("tray-square", "Square Shower Tray", "showering/shower-trays", 900, 45, 900, WHITE_SET),
    ("tray-rect", "Rectangular Shower Tray", "showering/shower-trays", 1200, 45, 800, WHITE_SET),
    ("tray-quadrant", "Quadrant Shower Tray", "showering/shower-trays", 900, 45, 900, WHITE_SET),
    # --- toilets (6) ---
    ("toilet-close-coupled", "Close Coupled Toilet", "toilets/close-coupled", 360, 780, 660, WHITE_SET),
    ("toilet-btw", "Back To Wall Toilet", "toilets/back-to-wall", 360, 800, 520, WHITE_SET),
    ("toilet-wall-hung", "Wall Hung Toilet", "toilets/wall-hung", 360, 360, 540, WHITE_SET),
    ("toilet-comfort", "Comfort Height Toilet", "toilets/close-coupled", 360, 850, 660, WHITE_SET),
    ("toilet-compact", "Compact Toilet", "toilets/close-coupled", 360, 750, 480, WHITE_SET),
    ("toilet-bidet", "Bidet", "toilets/bidets", 360, 800, 540, WHITE_SET),
    # --- basins (6) ---
    ("basin-pedestal", "Pedestal Basin", "basins/pedestal", 560, 820, 460, WHITE_SET),
    ("basin-wall-hung", "Wall Hung Basin", "basins/wall-hung", 600, 160, 420, WHITE_SET),
    ("basin-countertop-round", "Countertop Basin — Round", "basins/countertop", 400, 140, 400, WHITE_SET),
    ("basin-countertop-rect", "Countertop Basin — Rectangle", "basins/countertop", 550, 120, 380, WHITE_SET),
    ("basin-semi-recessed", "Semi-Recessed Basin", "basins/semi-recessed", 550, 170, 440, WHITE_SET),
    ("basin-cloakroom", "Cloakroom Handrinse Basin", "basins/cloakroom", 400, 140, 300, WHITE_SET),
    # --- vanity (8) ---
    ("vanity-standing-drawers", "Standing Vanity — Drawers", "furniture/vanity-units", 600, 850, 460, OAK_SET),
    ("vanity-standing-cupboard", "Standing Vanity — Cupboard", "furniture/vanity-units", 600, 850, 460, OAK_SET),
    ("vanity-standing-mix", "Standing Vanity — Drawer + Cupboard", "furniture/vanity-units", 800, 850, 460, OAK_SET),
    ("vanity-floating-drawers", "Floating Vanity — Drawers", "furniture/vanity-units", 600, 600, 460, OAK_SET),
    ("vanity-floating-cupboard", "Floating Vanity — Cupboard", "furniture/vanity-units", 600, 600, 460, OAK_SET),
    ("vanity-curved", "Curved Front Vanity", "furniture/vanity-units", 600, 850, 460, OAK_SET),
    ("vanity-combined-btw", "Combined Toilet + Basin Vanity", "furniture/vanity-units", 1200, 850, 460, WHITE_SET),
    ("vanity-basin-on-top", "Vanity with Countertop Basin", "furniture/vanity-units", 600, 850, 460, OAK_SET),
    # --- mirrors + cabinets (10) ---
    ("mirror-rect", "Rectangle Mirror", "mirrors-cabinets/mirrors", 600, 800, 20, CHROME_SET),
    ("mirror-rect-led", "Rectangle Mirror — LED Edge", "mirrors-cabinets/mirrors", 600, 800, 22, CHROME_SET),
    ("mirror-round", "Round Mirror", "mirrors-cabinets/mirrors", 600, 600, 20, CHROME_SET),
    ("mirror-round-led", "Round Mirror — LED Border", "mirrors-cabinets/mirrors", 600, 600, 22, CHROME_SET),
    ("mirror-oval", "Oval Mirror", "mirrors-cabinets/mirrors", 500, 800, 20, CHROME_SET),
    ("mirror-oval-led", "Oval Mirror — LED Border", "mirrors-cabinets/mirrors", 500, 800, 22, CHROME_SET),
    ("cabinet-1door", "Mirror Cabinet — 1 Door", "mirrors-cabinets/mirror-cabinets", 450, 700, 140, WHITE_SET),
    ("cabinet-2door", "Mirror Cabinet — 2 Door", "mirrors-cabinets/mirror-cabinets", 600, 700, 140, WHITE_SET),
    ("cabinet-3door", "Mirror Cabinet — 3 Door", "mirrors-cabinets/mirror-cabinets", 900, 700, 140, WHITE_SET),
    ("cabinet-4door", "Mirror Cabinet — 4 Door", "mirrors-cabinets/mirror-cabinets", 1200, 700, 140, WHITE_SET),
    # --- panel + taps + showers (5) ---
    ("panel-board", "Wall Panel Board", "tiles-panels", 2400, 1200, 9, WHITE_SET),
    ("tap-basin-mono", "Basin Mono Mixer Tap", "taps/basin-taps/mono", 50, 215, 175, CHROME_SET),
    ("tap-bath-filler", "Bath Filler Tap", "taps/bath-taps", 195, 215, 115, CHROME_SET),
    ("shower-head-fixed", "Fixed Shower Head + Arm", "showering/shower-heads", 200, 200, 360, CHROME_SET),
    ("shower-set-bar", "Bar Shower Set", "showering/shower-sets", 250, 1300, 450, CHROME_SET),
    # --- heating (6) ---
    ("radiator-panel", "Panel Radiator (Type 22)", "heating/radiators", 1200, 600, 100, ["white", "anthracite"]),
    ("radiator-flat-finned", "Flat Panel Radiator", "heating/radiators", 1200, 600, 80, ["white", "anthracite"]),
    ("radiator-column", "Column Radiator", "heating/radiators", 1000, 600, 100, ["white", "anthracite", "chrome"]),
    ("rail-round", "Towel Rail — Round Bars", "heating/towel-rails", 500, 1100, 80, CHROME_SET),
    ("rail-square", "Towel Rail — Square Bars", "heating/towel-rails", 500, 1100, 80, CHROME_SET),
    ("rail-floor", "Floor Standing Towel Rail", "heating/towel-rails", 500, 1100, 150, CHROME_SET),
]


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()

    retailer = db.scalar(select(Retailer).where(Retailer.slug == RETAILER["slug"]))
    if not retailer:
        retailer = Retailer(**RETAILER)
        db.add(retailer)
        db.commit()

    cat_ids = {}
    for c in db.scalars(select(Category)).all():
        cat_ids[c.slug] = c.id
    # ensure extra categories exist
    for slug, name, depth, parent_slug in EXTRA_CATEGORIES:
        if slug not in cat_ids:
            c = Category(slug=slug, name=name, depth=depth, icon="generic", sort_order=0)
            db.add(c)
            db.flush()
            cat_ids[slug] = c.id
    for slug, name, depth, parent_slug in EXTRA_CATEGORIES:
        if parent_slug:
            c = db.get(Category, cat_ids[slug])
            if c.parent_id is None:
                c.parent_id = cat_ids.get(parent_slug)
    db.commit()

    added = updated = missing = 0
    for slug, name, cat, w, h, d, finishes in CATALOG:
        glb = MODELS / f"{slug}.glb"
        thumb = ROOT / "assets" / "thumbnails" / f"{slug}.png"
        if not glb.exists():
            print(f"MISSING GLB: {slug}")
            missing += 1
            continue
        sku = f"GEN-{slug.upper()}"
        p = db.scalar(select(Product).where(
            Product.retailer_id == retailer.id, Product.retailer_sku == sku))
        if not p:
            p = Product(retailer_id=retailer.id, retailer_sku=sku, name=name,
                        brand="Generic", category=cat, category_id=cat_ids.get(cat))
            db.add(p)
            added += 1
        else:
            updated += 1
        p.name = name
        p.category = cat
        p.category_id = cat_ids.get(cat)
        p.price_gbp = 0
        p.price_note = "Generic catalogue model"
        p.price_is_from = False
        p.width_mm, p.height_mm, p.depth_mm = w, h, d
        p.dimensions_confidence = "high"
        p.placeholder_kind = "generic_shape"
        p.finishes = finishes
        p.model_url = f"/models/{slug}.glb"
        p.model_status = "ready"
        p.model_method = "parametric-mcp"
        p.thumbnail_url = f"/thumbnails/{slug}.png" if thumb.exists() else None
        p.main_image_url = p.thumbnail_url
        p.active = True
        p.in_stock = True
    db.commit()
    db.close()
    print(f"Seeded catalogue: added={added} updated={updated} missing_glb={missing} total={len(CATALOG)}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    main()
