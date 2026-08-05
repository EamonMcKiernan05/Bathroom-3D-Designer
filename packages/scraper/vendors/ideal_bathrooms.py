"""Ideal Bathrooms IoM (https://idealbathrooms.im/) — PRIORITY 1 (doc 02 §2.6).

Custom CMS (3 Legs Ltd), server-side rendered, no anti-bot. Small catalogue
(100-300 products). Category pages `/prod_cat/C_{cat}_{id}.shtml` list product
pages `/prod_cat/P_{name}_{id}.shtml`.

Product page structure (verified live 2026-08-03):
  <title>Name | Category | Ideal Bathrooms</title>
  Code AQ-T4
  Dimensions 380mm (Width) 670mm (Depth) 790mm (Height)
  Colour White  Material Ceramics
  &pound; 240.00 Inc VAT
  Stock: In-Stock
  images: images/{SKU}__________wi640he480moletterboxbg000.jpg  (size-suffixed)
"""
from __future__ import annotations

import html as htmlmod
import re

from ..shared.dimensions import extract_dimensions
from ..shared.normalize import normalize_colour, normalize_finish
from ..shared.prices import parse_price
from .base import VendorScraper

# Ideal category key (from URL C_<key>_<id>.shtml) -> normalized taxonomy slug.
# Mapped to the doc 02 taxonomy where possible; unmapped cats fall back to
# 'ideal-bathrooms/<key>' (doc 02 §6.4: categories split by vendor).
CATEGORY_MAP = {
    "toilets": "toilets",
    "toilet-seats": "ideal-bathrooms/toilet-seats",
    "vanity-units": "furniture/vanity-units",
    "combined-toilet-and-basin-units": "ideal-bathrooms/combined-units",
    "wash-basin-taps": "taps/basin-taps",
    "mono-block-tap": "taps/basin-taps/mono",
    "bath-taps": "taps/bath-taps",
    "kitchen-taps": "ideal-bathrooms/kitchen-taps",
    "taps": "taps",
    "shower-trays": "showering/shower-trays",
    "shower-doors": "showering/shower-screens",
    "shower-enclosures": "showering/shower-screens",
    "shower-packs": "showering/shower-sets",
    "shower-wall-panels": "tiles-panels/shower-wall-panels",
    "ceiling-panels": "tiles-panels/ceiling-panels",
    "flooring": "tiles-panels/floor-tiles",
    "j2-flooring": "tiles-panels/floor-tiles",
    "mirrors": "mirrors-cabinets/mirrors",
    "illuminated-mirrors": "mirrors-cabinets/illuminated-mirrors",
    "towel-radiators": "heating/towel-rails",
    "baths": "baths",
    "bath-screen": "showering/shower-screens",
    "bath-waste-kit": "accessories",
    "splash-bax": "tiles-panels/shower-wall-panels",
    "nuance-panels": "tiles-panels/shower-wall-panels",
    "perform-panel": "tiles-panels/shower-wall-panels",
    "brochures": "ideal-bathrooms/brochures",
}

_PROD_LINK = re.compile(r'href="(P_[^"]+\.shtml)"', re.I)
_STOCK = re.compile(r"Stock\s*:\s*(\w[\w\s\-]*)", re.I)


class IdealBathroomsScraper(VendorScraper):
    slug = "ideal-bathrooms"
    base_url = "https://idealbathrooms.im"
    # Exact category URLs crawled from the homepage (2026-08-03) — Ideal's
    # slugs have unpredictable trailing dashes, so no URL construction.
    start_categories = [
        ("toilets", "/prod_cat/C_toilets-_24.shtml"),
        ("toilet-seats", "/prod_cat/C_toilet-seats_25.shtml"),
        ("vanity-units", "/prod_cat/C_vanity-units_6.shtml"),
        ("combined-units", "/prod_cat/C_combined-toilet-and-basin-units_42.shtml"),
        ("wash-basin-taps", "/prod_cat/C_wash-basin-taps_19.shtml"),
        ("mono-block-tap", "/prod_cat/C_mono-block-tap_17.shtml"),
        ("bath-taps", "/prod_cat/C_bath-taps_21.shtml"),
        ("kitchen-taps", "/prod_cat/C_kitchen-taps-_45.shtml"),
        ("taps", "/prod_cat/C_taps-_47.shtml"),
        ("shower-trays", "/prod_cat/C_shower-trays_27.shtml"),
        ("shower-doors", "/prod_cat/C_shower-doors-_49.shtml"),
        ("shower-enclosures", "/prod_cat/C_shower-enclosures_54.shtml"),
        ("shower-packs", "/prod_cat/C_shower-packs_26.shtml"),
        ("shower-wall-panels", "/prod_cat/C_-shower-wall-panels-_40.shtml"),
        ("ceiling-panels", "/prod_cat/C_ceiling-panels-_43.shtml"),
        ("flooring", "/prod_cat/C_flooring-_41.shtml"),
        ("j2-flooring", "/prod_cat/C_j2-flooring-_65.shtml"),
        ("splash-bax", "/prod_cat/C_splash-bax-_68.shtml"),
        ("nuance-panels", "/prod_cat/C_nuance-panels-_60.shtml"),
        ("perform-panel", "/prod_cat/C_perform-panel-_58.shtml"),
        ("mirrors", "/prod_cat/C_mirrors-_29.shtml"),
        ("illuminated-mirrors", "/prod_cat/C_illuminated-mirrors_28.shtml"),
        ("towel-radiators", "/prod_cat/C_towel-radiators-_30.shtml"),
        ("baths", "/prod_cat/C_baths_14.shtml"),
        ("bath-screen", "/prod_cat/C_bath-screen_15.shtml"),
        ("bath-waste-kit", "/prod_cat/C_bath-waste-kit_16.shtml"),
        ("brochures", "/prod_cat/C_brochures-_55.shtml"),
    ]
    CATEGORY_MAP = CATEGORY_MAP

    def extract_from_category(self, html: str, category_url: str) -> list[dict] | None:
        """The brochures page (C_brochures-_55.shtml) is a DIRECTORY of brand
        brochures with no detail pages — each entry is brand name + cover
        image + external brand link. Extract them as catalogue entries
        directly, attributed to their brand (Armitage Shanks, EastBrook...).
        Return None for every other category (normal P_*.shtml crawl)."""
        if "C_brochures" not in category_url:
            return None
        entries = []
        # Each entry is `<a href=... title="BRAND"> <span.prod_image><img ...>
        # ... <h5 class="list_name">BRAND</h5>`. The wrapper div classes are
        # inconsistent across entries (only some carry `category_product`),
        # and nav/breadcrumb anchors earlier on the page also carry title=,
        # so walk backwards from each h5 to its nearest anchor (≤1500 chars
        # back) instead of matching forward.
        _h5 = re.compile(r'<h5 class="list_name">([^<]+)</h5>', re.I)
        _anchor = re.compile(r'<a href="([^"]+)" title="([^"]+)"[^>]*>', re.I)
        _img = re.compile(r'<img src="([^"]+)"', re.I)
        for m in _h5.finditer(html):
            brand = re.sub(r"\s+", " ", htmlmod.unescape(m.group(1))).strip()
            if not brand or brand.lower() == "test":
                continue
            window = html[max(0, m.start() - 1500):m.start()]
            am = None
            for am_c in _anchor.finditer(window):
                am = am_c  # keep the LAST (nearest) anchor before the h5
            if not am or am.group(2).strip().lower() != brand.lower():
                continue  # not a product entry (nav leftover)
            href = am.group(1)
            img_m = _img.search(window[am.end():])
            sku = "brochure-" + re.sub(r"[^a-z0-9]+", "-", brand.lower()).strip("-")
            imgs = []
            if img_m and "missing_catproduct" not in img_m.group(1):
                src = img_m.group(1)
                imgs.append(("/prod_cat/" + src) if src.startswith("images/") else src)
            entries.append({
                "retailer_sku": sku,
                "retailer_url": href,
                "name": f"{brand} Brochure",
                "brand": brand,
                "description": (
                    f"{brand} product brochure, available from Ideal Bathrooms "
                    f"Isle of Man. Source for wall/floor/ceiling patterns and "
                    f"bathroom furniture ranges."
                ),
                "price_gbp": None,
                "price_note": None,
                "price_is_from": False,
                "width_mm": None,
                "height_mm": None,
                "depth_mm": None,
                "diameter_mm": None,
                "dimensions_confidence": None,
                "finishes": [],
                "colours": [],
                "sizes": [],
                "image_urls": imgs,
                "in_stock": None,
                "category_key": "brochures",
                # brochures are reference material — nothing to model-generate
                "model_status": "ready",
            })
        return entries or None

    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        urls = []
        for m in _PROD_LINK.finditer(html):
            url = m.group(1)
            # category pages live under /prod_cat/; relative product links resolve there
            if url.startswith("/prod_cat/"):
                full = url
            elif url.startswith("/"):
                full = url
            else:
                full = f"/prod_cat/{url}"
            if full not in urls:
                urls.append(full)
        return urls

    def extract_product(self, html: str, url: str) -> dict | None:
        text = htmlmod.unescape(html)
        # title -> product name
        m = re.search(r"<title>\s*(.*?)\s*\|", text, re.I | re.S)
        name = m.group(1).strip() if m else None
        if not name:
            m = re.search(r"<title>\s*(.*?)\s*</title>", text, re.I | re.S)
            name = m.group(1).strip() if m else None
        if not name:
            return None
        name = re.sub(r"\s+", " ", name).strip()

        # SKU — the product code sits after the "Code" attrib_label span
        # (e.g. ...>Code</span> <span itemprop='productID' ...>AQ-T2</span>)
        sku = None
        m = re.search(
            r'<span[^>]*class="attrib_label"[^>]*>Code</span>\s*<span[^>]*>([^<]+)</span>', text, re.I
        )
        if m:
            sku = m.group(1).strip()
        if not sku:
            # fall back to the code prefix of the first product image (AQ-T2_______...)
            m = re.search(r"images/([A-Za-z0-9_\-]+?)_*wi\d+he\d+", text, re.I)
            if m:
                sku = m.group(1).strip("_") or None
        if not sku:
            sku = url.rsplit("_", 1)[0].split("P_", 1)[-1]

        # price
        price = parse_price(text)

        # dimensions — Ideal's labelled format handled by extract_dimensions(vendor=...)
        dims = extract_dimensions(text, vendor="ideal-bathrooms")
        confidence = dims.pop("confidence")

        # finish/colour
        finish = None
        colour = None
        m = re.search(r"Colour\s*[:]?\s*([A-Za-z][A-Za-z\s\-/]*)", text)
        if m:
            colour = normalize_colour(m.group(1).strip())
            finish = normalize_finish(m.group(1).strip())

        # stock
        in_stock = None
        m = _STOCK.search(text)
        if m:
            in_stock = "in" in m.group(1).lower()

        # images — keep the LARGEST variant per product (Ideal has no bare
        # 'original' URL; wi640he480 is the top resolution, verified live)
        imgs = []
        variants: dict[str, tuple[int, str]] = {}  # base_code -> (res, url)
        for m in re.finditer(r'(?:src|href)="([^"]*images/[A-Za-z0-9_\-]+\.(?:jpg|jpeg|png|webp))"', text, re.I):
            raw = m.group(1)
            if not re.search(r"wi\d+he\d+", raw):
                continue
            base = re.sub(r"wi\d+he\d+.*?\.(jpg|jpeg|png|webp)$", "", raw, flags=re.I)
            mm = re.search(r"wi(\d+)he(\d+)", raw)
            res = int(mm.group(1)) * int(mm.group(2)) if mm else 0
            if base not in variants or res > variants[base][0]:
                variants[base] = (res, raw)
        # image URLs are relative to /prod_cat/ on this site — prefix so abs_url resolves
        imgs = [("/prod_cat/" + v[1]) if v[1].startswith("images/") else v[1]
                for _, v in sorted(variants.items(), key=lambda kv: -kv[1][0])]
        if not imgs:
            # fall back to og:image
            m = re.search(r'property="og:image"\s+content="([^"]+)"', text, re.I)
            if m:
                imgs = [m.group(1)]

        return {
            "retailer_sku": sku,
            "retailer_url": url,
            "name": name,
            "brand": None,
            "description": None,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"],
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [finish] if finish else [],
            "colours": [colour] if colour else [],
            "sizes": [],
            "image_urls": imgs,
            "in_stock": in_stock,
            "category_key": None,  # set by base from the category loop
        }
