"""Parse marketing-format brochures (no price tables) into rows JSON
compatible with load_brochure.py:

- Armitage Shanks B2C MEG: product blocks = heading + bullet features
  ending in an SKU code (X036201 / T333001 / B9780AA ...). Dims come from
  name patterns like "Washbasin 60x49cm".
- Scudo New Product Guide / Edition Twenty Two: spread pages with a loud
  product NAME and body copy like "The Lira 1700 x 750mm Freestanding Bath".

Output rows: {page, name, sku, price_gbp, dims, category, image, ...}
"""
import fitz
import json
import os
import re
import sys

OUT_ROOT = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures"

# Armitage Shanks SKU codes: letter(s) + 5-6 digits, optionally 2 letters.
# (the printed Greek Chi Χ035601 counts too)
AS_SKU = re.compile(r"[XTWSBΧX][0-9]{5,6}(?:AA)?")
AS_DIMS = re.compile(r"(\d{2,3})\s*(?:x|×)\s*(\d{2,3})\s*cm", re.I)
SCUDO_DIMS = re.compile(r"(\d{3,4})\s*(?:x|×)\s*(\d{3,4})\s*mm", re.I)

CAT_RULES = [
    (re.compile(r"bidet", re.I), "basins"),
    (re.compile(r"washbasin|basin|vessel|counter top|sink", re.I), "basins"),
    (re.compile(r"close[d]? coupled|back[- ]?to[- ]?wall|wall hung|bowl|wc|toilet|pack", re.I), "toilets"),
    (re.compile(r"bath\b|bathtub|freestanding bath", re.I), "baths"),
    (re.compile(r"shower", re.I), "showering"),
    (re.compile(r"mixer|tap|monobloc", re.I), "taps"),
    (re.compile(r"mirror", re.I), "mirrors-cabinets/mirrors"),
    (re.compile(r"furniture|vanity|cabinet", re.I), "furniture/vanity-units"),
    (re.compile(r"tray", re.I), "showering/shower-trays"),
]


def categorize(text: str) -> str:
    for rx, cat in CAT_RULES:
        if rx.search(text):
            return cat
    return None


def clean(txt: str) -> str:
    words = txt.split()
    out = []
    for w in words:
        if out and w.lower() == out[-1].lower():
            continue
        out.append(w)
    return " ".join(out)


def page_blocks(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        spans = [(s["text"], s["size"]) for l in b["lines"] for s in l["spans"]]
        txt = " ".join(s[0] for s in spans).strip()
        if txt:
            size = max((s[1] for s in spans), default=10)
            out.append((b["bbox"][0], b["bbox"][1], b["bbox"][2], b["bbox"][3], txt, size))
    return out


def match_image(page, bbox, images, max_dx=300):
    bx0, by0, bx1, by1 = bbox
    best, best_d = None, 1e18
    for bb, xref in images:
        icx = (bb.x0 + bb.x1) / 2
        if abs(icx - (bx0 + bx1) / 2) > max_dx:
            continue
        if bb.y1 <= by0:
            d = by0 - bb.y1
        elif bb.y0 >= by1:
            d = bb.y0 - by1
        else:
            d = 0
        if d < best_d:
            best, best_d = (bb, xref), d
    return best


def render_crop(page, rect, out_path, zoom=2.0):
    clip = fitz.Rect(rect.x0 - 6, rect.y0 - 6, rect.x1 + 6, rect.y1 + 6) & page.rect
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
    pix.save(out_path)


def parse_armitage(path, out_dir, brand):
    doc = fitz.open(path)
    rows = []
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = page_blocks(page)
        imgs = []
        for im in page.get_images(full=True):
            try:
                imgs.append((page.get_image_bbox(im), im[0]))
            except Exception:
                pass
        # group bullets: a bullet containing an SKU anchors a product entry
        for b in blocks:
            x0, y0, x1, y1, txt, size = b
            m = AS_SKU.search(txt)
            if not m or not txt.strip().startswith("•"):
                continue
            sku = m.group(0).replace("Χ", "X")
            # heading: nearest block ABOVE with bigger font, overlapping column
            cands = []
            for hb in blocks:
                hx0, hy0, hx1, hy1, htxt, hsize = hb
                if hy1 > y0 + 2 or hsize < size + 1.5:
                    continue
                ov = max(0.0, min(hx1, x1) - max(hx0, x0))
                if ov < 30 and abs((hx0 + hx1) / 2 - (x0 + x1) / 2) > 120:
                    continue
                cands.append((y0 - hy1, hb))
            name = None
            anchor = b[:4]
            if cands:
                cands.sort(key=lambda t: t[0])
                nb = cands[0][1]
                name = clean(nb[4])
                # never let an SKU code or a second product's line leak into
                # the name (merged headings) — cut at the first SKU token
                name = AS_SKU.sub("", name).strip(" •-")
                name = re.sub(r"\s{2,}", " ", name)
                anchor = (min(nb[0], x0), nb[1], max(nb[2], x1), y1)
            dims = {"width_mm": None, "depth_mm": None, "height_mm": None}
            dm = AS_DIMS.search(name or txt)
            if dm:
                dims["width_mm"] = int(dm.group(1)) * 10
                dims["depth_mm"] = int(dm.group(2)) * 10
            rows.append({
                "page": pno,
                "name": clean(name or f"{brand} product"),
                "sku": sku,
                "price_gbp": None,
                "dims": dims,
                "hand": None,
                "size_raw": (dm.group(0) if dm else ""),
                "category": categorize((name or "") + " " + txt),
                "image": None,
                "_anchor": anchor,
                "_section": "",
            })
    doc.close()
    return attach_images(path, rows, out_dir)


def parse_scudo(path, out_dir, brand):
    doc = fitz.open(path)
    rows = []
    seen = set()
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = page_blocks(page)
        imgs = []
        for im in page.get_images(full=True):
            try:
                imgs.append((page.get_image_bbox(im), im[0]))
            except Exception:
                pass
        # heading = largest-font block on the page
        if not blocks:
            continue
        big = max(blocks, key=lambda b: b[5])
        name = clean(big[4]).title()
        if len(name) > 40 or not re.search(r"[A-Za-z]{3}", name):
            continue
        # find dims + product type in the page body — SKIP pages without any
        # real product dimensions (covers, contents, blurb pages)
        body = " ".join(b[4] for b in blocks)
        dm = SCUDO_DIMS.search(body)
        if not dm:
            continue
        dims = {"width_mm": None, "depth_mm": None, "height_mm": None}
        size_raw = ""
        if dm:
            dims["width_mm"] = int(dm.group(1))
            dims["depth_mm"] = int(dm.group(2))
            size_raw = dm.group(0)
        # type = the 1-4 words right after the dims ("...Freestanding Bath");
        # stop at verbs so marketing prose doesn't leak into the name
        m = re.search(
            r"\d{3,4}\s*(?:x|×)\s*\d{3,4}\s*mm\s+((?:[A-Z][a-z\-]+ ?){1,4})", body
        )
        ptype = m.group(1).strip() if m else ""
        ptype = re.split(r"\b(delivers|sits|balances|features|offers|combines)\b", ptype)[0].strip()
        key = (name, size_raw)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "page": pno,
            "name": f"{name} {ptype}".strip() if ptype else name,
            "sku": f"SCUDO-{re.sub(r'[^A-Z0-9]+', '', name.upper())[:18]}-{pno:02d}",
            "price_gbp": None,
            "dims": dims,
            "hand": None,
            "size_raw": size_raw,
            "category": categorize(ptype + " " + body[:600]),
            "image": None,
            "_anchor": big[:4],
            "_section": "",
        })
    doc.close()
    return attach_images(path, rows, out_dir)


def attach_images(path, rows, out_dir):
    """Second pass: reopen the PDF once and attach image crops."""
    doc = fitz.open(path)
    os.makedirs(out_dir, exist_ok=True)
    for r in rows:
        page = doc[r["page"]]
        imgs = []
        for im in page.get_images(full=True):
            try:
                imgs.append((page.get_image_bbox(im), im[0]))
            except Exception:
                pass
        hit = match_image(page, r["_anchor"], imgs)
        if hit:
            bb, xref = hit
            fn = f"p{r['page']:03d}_{re.sub(r'[^A-Za-z0-9_-]', '', r['sku'])}.png"
            render_crop(page, bb, os.path.join(out_dir, fn))
            r["image"] = fn
        del r["_anchor"]
    doc.close()
    return rows


def main():
    jobs = [
        ("armitage-shanks", "Armitage-Shanks_B2C_MEG.pdf", "Armitage Shanks", parse_armitage),
        ("scudo", "New-Product-Guide_LR.pdf", "Scudo", parse_scudo),
    ]
    for brand_dir, fn, brand, parser in jobs:
        path = os.path.join(OUT_ROOT, brand_dir, fn)
        out_dir = os.path.join(OUT_ROOT, brand_dir, "extracted")
        rows = parser(path, out_dir, brand)
        # dedupe SKUs
        seen, deduped = set(), []
        for r in rows:
            if r["sku"] in seen:
                continue
            seen.add(r["sku"])
            deduped.append(r)
        out = os.path.join(OUT_ROOT, brand_dir, f"{brand_dir}_rows.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(deduped, f, indent=1)
        from collections import Counter

        print(f"\n{brand}: {len(deduped)} products -> {out}")
        print("  categories:", dict(Counter(r['category'] for r in deduped)))
        print("  with image:", sum(1 for r in deduped if r["image"]))
        for r in deduped[:8]:
            print(f"    p{r['page']:2d} {r['sku']:14s} {r['name'][:48]}")


if __name__ == "__main__":
    main()
