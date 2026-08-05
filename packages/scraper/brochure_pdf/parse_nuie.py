"""Parse Nuie full brochure (123pp) product pages into catalogue rows.

Layout (verified p59-61):
- spread pages, each holding 1-4 product blocks
- block = product NAME text block, then a "Size [Hand] Code Price" header,
  then spec rows: "L1700 x W700 x D400mm NBA909 £437.00"
- product photo placed near (usually directly above) the name block

Outputs rows JSON + rendered product-image crops.
"""
import fitz
import json
import os
import re
import sys

PDF = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\nuie-bathrooms\nuie-full-brochure-jan-25-lr.pdf"
OUT_DIR = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\nuie-bathrooms\extracted"
os.makedirs(OUT_DIR, exist_ok=True)

HEADER_RE = re.compile(r"^size\b.*\bcode\b.*\bprice\b", re.I)
# Spec row formats (tried in priority order):
#  3D: "L1700 x W700 x D400mm NBA909 £437.00" (letters may prefix each number)
#  2D: "900 x 900mm AQU9N-E8 £738.00" (square enclosures etc.)
#  1D: "800mm AQHD80N-E8 £493.00" (single width/size)
# Optional Left/Right hand between size and code.
ROW_RES = [
    re.compile(
        r"[LWH]?\s*(\d{3,4})\s*(?:x|×)\s*[WHD]?\s*(\d{3,4})"
        r"\s*(?:x|×)\s*[WHD]?\s*(\d{3,4})\s*mm"
        r"(?:\s+(Left|Right))?"
        r"\s+([A-Z][A-Z0-9]{2,14}[A-Z0-9\-]*)"
        r"\s+£\s*([\d,]+(?:\.\d{2})?)",
        re.I,
    ),
    re.compile(
        r"(\d{3,4})\s*(?:x|×)\s*(\d{3,4})\s*mm"
        r"(?:\s+(Left|Right))?"
        r"\s+([A-Z][A-Z0-9]{2,14}[A-Z0-9\-]*)"
        r"\s+£\s*([\d,]+(?:\.\d{2})?)",
        re.I,
    ),
    re.compile(
        r"(\d{3,4})\s*mm"
        r"(?:\s+(Left|Right))?"
        r"\s+([A-Z][A-Z0-9]{2,14}[A-Z0-9\-]*)"
        r"\s+£\s*([\d,]+(?:\.\d{2})?)",
        re.I,
    ),
]
ROW_KIND = ["3d", "2d", "1d"]
NAME_SKIP = re.compile(r"^(size|code|price|hand|all prices|nuie\.com|\d+\s*\d*$|suitable|panel|shown with|optional)", re.I)


def page_blocks(page):
    """Text blocks as (x0,y0,x1,y1,text)."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        txt = " ".join(s["text"] for l in b["lines"] for s in l["spans"]).strip()
        if txt:
            out.append((b["bbox"][0], b["bbox"][1], b["bbox"][2], b["bbox"][3], txt))
    return out


def page_section(blocks):
    """Section label from the page's top-left header block (y < 120).
    e.g. 'baths baths imperial baths thin-edge' or 'enclosures enclosures lucie 8mm'."""
    cands = [b for b in blocks if b[1] < 120 and b[3] - b[1] > 20]
    if not cands:
        return ""
    cands.sort(key=lambda b: (b[1], b[0]))
    return cands[0][4].lower()


def clean_block_text(txt: str) -> str:
    """Collapse whitespace and drop duplicate consecutive words — PDF text
    blocks on brochure name rows often overlap ('quadrant quadrant offset
    quadrant offset quadrant')."""
    words = txt.split()
    out: list[str] = []
    for w in words:
        if out and w.lower() == out[-1].lower():
            continue
        out.append(w)
    # also drop a leading repeat of the whole tail (e.g. 'a b a b')
    n = len(out)
    if n >= 2 and n % 2 == 0:
        half = n // 2
        if [x.lower() for x in out[:half]] == [x.lower() for x in out[half:]]:
            out = out[:half]
    return " ".join(out)


def parse_page(page, pno):
    blocks = page_blocks(page)
    headers = [b for b in blocks if HEADER_RE.match(b[4])]
    if not headers:
        return []
    # candidate name rows: blocks NOT matching header/skip patterns
    products = []
    for h in headers:
        hx0, hy0, hx1, hy1, _ = h
        hcx = (hx0 + hx1) / 2
        hwidth = max(hx1 - hx0, 40)
        # name = nearest text block ABOVE the header whose column band
        # overlaps the header band by >= 40% (centres alone mis-match
        # adjacent columns on multi-product pages)
        name_cands = []
        for b in blocks:
            if b is h or HEADER_RE.match(b[4]):
                continue
            x0, y0, x1, y1, txt = b
            if y1 > hy0 + 2:
                continue  # not above
            if NAME_SKIP.match(txt.split("\n")[0]):
                continue
            # spec-row blocks (belonging to the product ABOVE) can sit above
            # a header — never treat a row as a name
            if any(rx.search(txt) for rx in ROW_RES):
                continue
            # horizontal band overlap
            ov = max(0.0, min(x1, hx1) - max(x0, hx0))
            bw = max(x1 - x0, 20)
            if ov / min(bw, hwidth) < 0.4 and abs((x0 + x1) / 2 - hcx) > 90:
                continue
            name_cands.append((hy0 - y1, b))  # distance above header
        if not name_cands:
            continue
        name_cands.sort(key=lambda t: t[0])
        name_txt = clean_block_text(name_cands[0][1][4])
        # spec rows: blocks below header, same x band, matching a row format
        rows = []
        for b in blocks:
            x0, y0, x1, y1, txt = b
            cx = (x0 + x1) / 2
            if abs(cx - (hx0 + hx1) / 2) > 140:
                continue
            if y0 < hy1 - 2:
                continue
            for line in txt.split("\n"):
                for kind, rx in zip(ROW_KIND, ROW_RES):
                    m = rx.search(line)
                    if m:
                        rows.append((kind, m))
                        break
        if not rows:
            continue
        products.append({
            "header_bbox": (hx0, hy0, hx1, hy1),
            "name": name_txt,
            "name_bbox": name_cands[0][1][:4],
            "rows": rows,
        })
    return products


def match_image(page, block_bbox, images):
    """Pick the product photo nearest the block, overlapping in x."""
    bx0, by0, bx1, by1 = block_bbox
    bcx = (bx0 + bx1) / 2
    best, best_d = None, 1e18
    for bb, xref in images:
        ix0, iy0, ix1, iy1 = bb
        # must horizontally overlap the block's column (±150)
        if ix1 < bx0 - 150 or ix0 > bx1 + 150:
            continue
        icx = (ix0 + ix1) / 2
        if abs(icx - bcx) > 250:
            continue
        # vertical distance between image edge and block
        if iy1 <= by0:
            d = by0 - iy1
        elif iy0 >= by1:
            d = iy0 - by1
        else:
            d = 0
        if d < best_d:
            best, best_d = (bb, xref), d
    return best


def render_crop(page, rect, out_path, zoom=2.2):
    clip = fitz.Rect(rect)
    # pad
    clip = fitz.Rect(clip.x0 - 6, clip.y0 - 6, clip.x1 + 6, clip.y1 + 6)
    clip = clip & page.rect
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=clip, alpha=False)
    pix.save(out_path)
    return pix.width, pix.height


def main():
    doc = fitz.open(PDF)
    all_products = []
    diag = {"pages_with_header": [], "pages_header_no_rows": []}
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = page_blocks(page)
        has_header = any(HEADER_RE.match(b[4]) for b in blocks)
        if has_header:
            diag["pages_with_header"].append(pno)
        imgs = []
        for im in page.get_images(full=True):
            try:
                imgs.append((page.get_image_bbox(im), im[0]))
            except Exception:
                pass
        prods = parse_page(page, pno)
        if has_header and not prods:
            diag["pages_header_no_rows"].append(pno)
        section = page_section(blocks)
        # page-level feature height (enclosures list "Height 1900mm" in the
        # features block) — applies to every enclosure row on the page
        feat_h = None
        for b in blocks:
            m = re.search(r"Height\s*(\d{3,4})\s*mm", b[4], re.I)
            if m:
                feat_h = int(m.group(1))
                break
        for p in prods:
            # block anchor = name bbox if above header, else header bbox
            nb = p["name_bbox"]
            anchor = (nb[0], nb[1], nb[2], nb[3])
            hit = match_image(page, anchor, imgs) or match_image(page, p["header_bbox"], imgs)
            img_file = None
            sku_first = None
            for kind, m in p["rows"]:
                if kind == "3d":
                    sku_first = m.group(5)
                elif kind == "2d":
                    sku_first = m.group(4)
                else:
                    sku_first = m.group(3)
                break
            if hit and sku_first:
                bb, xref = hit
                img_file = f"p{pno:03d}_{re.sub(r'[^A-Za-z0-9_-]', '', sku_first)}.png"
                w, h = render_crop(page, bb, os.path.join(OUT_DIR, img_file))
            for kind, m in p["rows"]:
                if kind == "3d":
                    dims = {"width_mm": int(m.group(1)), "depth_mm": int(m.group(2)), "height_mm": int(m.group(3))}
                    hand, sku, price = m.group(4), m.group(5), m.group(6)
                elif kind == "2d":
                    dims = {"width_mm": int(m.group(1)), "depth_mm": int(m.group(2)), "height_mm": None}
                    hand, sku, price = m.group(3), m.group(4), m.group(5)
                else:
                    dims = {"width_mm": int(m.group(1)), "depth_mm": None, "height_mm": None}
                    hand, sku, price = m.group(2), m.group(3), m.group(4)
                # section-aware mapping. Nuie rows are "L x W x D" plan dims;
                # for baths the 3rd number is INTERNAL depth, not height —
                # standard bath height ~400mm applied by the model builder.
                if "bath" in section:
                    dims = {"width_mm": dims["width_mm"], "depth_mm": dims["depth_mm"],
                            "height_mm": None, "internal_depth_mm": dims.get("height_mm")}
                    category = "baths"
                    nm = p["name"].lower()
                    if "double ended" in nm:
                        category = "baths/double-ended"
                    elif "single ended" in nm:
                        category = "baths/single-ended"
                    elif "shower bath" in nm or "b-bath" in nm or "p-bath" in nm:
                        category = "baths/shower-bath"
                    elif "freestanding" in nm:
                        category = "baths/freestanding"
                elif "enclosure" in section or "shower" in section:
                    dims["height_mm"] = dims.get("height_mm") or feat_h
                    category = "showering/shower-enclosures"
                elif "basin" in section or "sink" in section:
                    category = "basins"
                elif "toilet" in section or "wc" in section:
                    category = "toilets"
                elif "furniture" in section or "vanity" in section:
                    category = "furniture/vanity-units"
                elif "mirror" in section:
                    category = "mirrors-cabinets/mirrors"
                elif "radiator" in section or "towel" in section:
                    category = "heating/towel-rails"
                elif "tap" in section or "brassware" in section:
                    category = "taps"
                else:
                    category = None
                all_products.append({
                    "page": pno,
                    "name": p["name"],
                    "section": section,
                    "category": category,
                    "size_raw": m.group(0),
                    "dims": dims,
                    "hand": hand,
                    "sku": sku,
                    "price_gbp": float(price.replace(",", "")),
                    "image": img_file,
                })
    doc.close()
    out = os.path.join(os.path.dirname(OUT_DIR), "nuie_rows.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=1)
    print(f"{len(all_products)} product variants on {len(set(p['page'] for p in all_products))} pages -> {out}")
    print("pages with spec header:", diag["pages_with_header"])
    print("pages header-but-no-rows:", diag["pages_header_no_rows"])
    # sample
    for p in all_products[:8]:
        print(f"  p{p['page']:3d} {p['sku']:10s} £{p['price_gbp']:8.2f} {p['dims']} img={p['image']} | {p['name'][:45]}")


if __name__ == "__main__":
    main()
