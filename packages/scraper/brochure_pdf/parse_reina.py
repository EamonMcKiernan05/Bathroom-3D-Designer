"""Parse Reina radiator brochures (REINA-DESIGN-web.pdf, v-by-reina, electric).

Layout (verified p10/p12): an "Image shown N column HxW Colour" caption,
optionally a product heading (COLONA 2 COLUMN HORIZONTAL WHITE), then a spec
table: rows of [height, width, pipe centres, wall-to-pipe, wall distance,
fuel, btu, watts, £ex.VAT, £RRP...]. Output rows JSON for load_brochure.py.
Radiators all become category heating/towel-rails (parametric builder).
"""
import fitz
import json
import os
import re
import sys

OUT_ROOT = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures"

CAPTION_RE = re.compile(
    r"Image shown\s+(\d+)\s+column(?:s)?\s+(\d{3,4})\s*(?:x|×)\s*(\d{3,4})\s*([A-Za-z ]+)?",
    re.I,
)
HEADING_RE = re.compile(r"^([A-Z0-9 ]{6,45}(?:WHITE|BLACK|GREY|CHROME|ANTHRACITE|STAINLESS|RAL)?)\s*$")
PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)")
NUM_RE = re.compile(r"^\d{2,4}$")


def page_blocks(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        txt = " ".join(s["text"] for l in b["lines"] for s in l["spans"]).strip()
        if txt:
            out.append((b["bbox"][0], b["bbox"][1], b["bbox"][2], b["bbox"][3], txt))
    return out


def parse_pdf(path, brand):
    doc = fitz.open(path)
    rows = []
    for pno in range(doc.page_count):
        page = doc[pno]
        txt = page.get_text("text")
        if "£" not in txt:
            continue
        blocks = page_blocks(page)
        # captions + headings on the page
        caption = None
        for b in blocks:
            m = CAPTION_RE.search(b[4])
            if m:
                caption = m
                break
        heading = None
        for b in blocks:
            if HEADING_RE.match(b[4].strip()):
                heading = b[4].strip()
                break
        if not caption and not heading:
            continue
        # spec rows: lines that start height,width,... and contain a price.
        # Parse the raw text stream line by line; a row is: number number
        # number number number fuel number number £price
        lines = [l.strip() for l in txt.split("\n") if l.strip()]
        i = 0
        row_vals = []
        while i < len(lines):
            if NUM_RE.match(lines[i]):
                # collect the run of numeric/short-token lines until a price
                run = []
                j = i
                while j < len(lines) and not PRICE_RE.search(lines[j]):
                    run.append(lines[j])
                    j += 1
                    if len(run) > 10:
                        break
                if j < len(lines) and PRICE_RE.search(lines[j]):
                    run.append(lines[j])
                    nums = [r for r in run[:8] if re.match(r"^\d+$", r)]
                    if len(nums) >= 4:  # height, width, + at least pipe centres/wall
                        price_m = PRICE_RE.search(lines[j])
                        row_vals.append((nums, price_m.group(1)))
                    i = j + 1
                    continue
            i += 1
        if not row_vals:
            continue
        # name
        if caption:
            name = f"{caption.group(1)} Column Radiator {caption.group(2)}x{caption.group(3)}mm"
            colour = (caption.group(4) or "").strip()
            if colour:
                name += f" {colour.title()}"
        else:
            name = heading.title()
        sku_base = re.sub(r"[^A-Z0-9]+", "-", name.upper())[:24].strip("-")
        for k, (nums, price) in enumerate(row_vals):
            height, width = int(nums[0]), int(nums[1])
            rows.append({
                "page": pno,
                "name": f"{name} {height}x{width}",
                "sku": f"REINA-{sku_base}-{height}X{width}",
                "price_gbp": float(price.replace(",", "")),
                "price_note": "ex VAT",
                "dims": {"height_mm": height, "width_mm": width, "depth_mm": None},
                "hand": None,
                "size_raw": f"{height} x {width}mm",
                "category": "heating/towel-rails",
                "image": None,
            })
    doc.close()
    return rows


def attach_images(path, rows):
    """Attach the product photo above the spec table on each page."""
    doc = fitz.open(path)
    by_page = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    for pno, page_rows in by_page.items():
        page = doc[pno]
        # largest non-background image above the spec table region (y < 400)
        best = None
        best_area = 0
        for im in page.get_images(full=True):
            try:
                bb = page.get_image_bbox(im)
            except Exception:
                continue
            if bb.y1 > 420:
                continue  # spec table region is lower
            area = (bb.x1 - bb.x0) * (bb.y1 - bb.y0)
            if area > best_area and area > 3000:
                best, best_area = bb, area
        if best:
            out_dir = os.path.join(os.path.dirname(path), "extracted")
            os.makedirs(out_dir, exist_ok=True)
            for r in page_rows[:1]:  # one image per page, first product
                clip = fitz.Rect(best.x0 - 4, best.y0 - 4, best.x1 + 4, best.y1 + 4) & page.rect
                pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), clip=clip, alpha=False)
                fn = f"p{pno:03d}_{r['sku'][:28]}.png"
                pix.save(os.path.join(out_dir, fn))
                r["image"] = fn
    doc.close()
    return rows


def main():
    jobs = [
        ("reinadesign", "REINA-DESIGN-web.pdf"),
        ("reinadesign", "v-by-reina-brochure-full.pdf"),
        ("reinadesign", "REINA-2025-ELECTRIC-compressed.pdf"),
    ]
    all_rows = []
    for brand_dir, fn in jobs:
        path = os.path.join(OUT_ROOT, brand_dir, fn)
        rows = parse_pdf(path, "Reinadesign")
        rows = attach_images(path, rows)
        print(f"{fn}: {len(rows)} radiator variants")
        all_rows.extend(rows)
    # dedupe by sku
    seen, deduped = set(), []
    for r in all_rows:
        if r["sku"] in seen:
            continue
        seen.add(r["sku"])
        deduped.append(r)
    out = os.path.join(OUT_ROOT, "reinadesign", "reinadesign_rows.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=1)
    print(f"\nTOTAL: {len(deduped)} -> {out}")
    for r in deduped[:8]:
        print(f"  p{r['page']:3d} {r['sku'][:40]:40s} £{r['price_gbp']:8.2f} {r['name'][:40]}")


if __name__ == "__main__":
    main()
