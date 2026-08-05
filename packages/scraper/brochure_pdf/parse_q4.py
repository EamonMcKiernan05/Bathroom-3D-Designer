"""Parse Q4 catalogue PDF (377pp) — spatial column-aware association.

Multi-column spread pages break a sequential heading scan. Instead:
  1. collect all spans with bbox + font
  2. headings = Lato-Heavy lines (>=7.75pt) — each with bbox
  3. code rows = a y-row containing a Q4-code and a £ price — with bbox
  4. each code row attaches to the nearest heading ABOVE it whose x-column
     overlaps (same product box), else to a finish name on the same y-row.
Finish detection: the text cell on the code row that is neither code nor price.
"""
import fitz
import json
import os
import re

PDF = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\q4-bathrooms\Q4-Bathroom-2026.2_LR_Pages.pdf"

CODE_RE = re.compile(r"\b(Q4-\d{4,6})\b")
PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)")
DIMS_RE = re.compile(r"H(\d{2,4})\s*W(\d{2,4})\s*D(\d{2,4})")
FINISH_HINT = re.compile(r"^(gloss|matt?e|super\s+matt|havana|carbon|henley|soft|oak|walnut|"
                         r"white|grey|gray|blue|black|green|cashmere|indigo|khaki|olive|"
                         r"espresso|beige|sandy|brushed|chrome|brass|gun\s?metal|stone|"
                         r"slate|natural|satin|le?vanto|rimless$)", re.I)
# junk name cells that never describe a product
JUNK_NAME = re.compile(r"^(finish|code|rrp\b|new\b|\d+\s*$|"
                       r"£[\d,]+|q4-\d+|\d+\s*x\s*\d+|\d{3,4}\b|"
                       r"\d{3,4}\s*x\s*\d{2,4}|chrome\s+\d+)", re.I)
SECTION_WORDS = {"SANITARYWARE", "BATHS", "BATH", "FURNITURE", "SHOWERING", "ENCLOSURES",
                 "TAPS", "BRASSWARE", "MIRRORS", "RADIATORS", "ACCESSORIES", "PANELS",
                 "SHOWER TRAYS", "BATHSCREENS", "WET ROOMS", "WALL PANELS", "HEATING"}
EXCLUDE_RE = re.compile(
    r"\bwastes?\b|\boverflows?\b|\btraps?\b|\bpipework?\b|\bdrains?\b|"
    r"\bfixings?\b|\bseals?\b|\bgaskets?\b|\bcartridges?\b|\bspares?\b", re.I)


def spans(doc, pno):
    out = []
    for b in doc[pno].get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            if not l["spans"]:
                continue
            x0 = l["bbox"][0]; y = l["bbox"][1]
            # merge consecutive spans on the same line into cells by x gaps
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if not txt:
                continue
            size = max(s["size"] for s in l["spans"])
            font = l["spans"][0]["font"]
            out.append({"x0": x0, "y": y, "size": size, "font": font, "text": txt})
    return out


def parse_page(doc, pno):
    ss = spans(doc, pno)
    if not any(PRICE_RE.search(s["text"]) and CODE_RE.search(s["text"]) for s in ss):
        # also handle code & price on separate spans at same y
        pass
    has_price = any(PRICE_RE.search(s["text"]) for s in ss)
    if not has_price:
        return []

    headings = [s for s in ss if "Heavy" in s["font"] or s["size"] >= 7.75]
    # dims lines
    dims_by_col = []  # (x0, y, dims)
    for s in ss:
        dm = DIMS_RE.search(s["text"])
        if dm:
            dims_by_col.append((s["x0"], s["y"],
                                {"height_mm": int(dm.group(1)), "width_mm": int(dm.group(2)), "depth_mm": int(dm.group(3))}))

    # group rows by y (within 2px)
    rows = {}
    for s in ss:
        key = round(s["y"] / 2) * 2
        rows.setdefault(key, []).append(s)

    products = []
    for y in sorted(rows):
        cells = sorted(rows[y], key=lambda c: c["x0"])
        line_text = " ".join(c["text"] for c in cells)
        cm = CODE_RE.search(line_text)
        pm = PRICE_RE.search(line_text)
        if not (cm and pm):
            continue
        code = cm.group(1)
        price = float(pm.group(1).replace(",", ""))
        x0 = cells[0]["x0"]

        # name cell: the cell(s) that are neither the code nor the price
        name_parts = []
        for c in cells:
            t = c["text"]
            if CODE_RE.search(t) or PRICE_RE.search(t):
                continue
            up = t.upper()
            if up in ("CODE", "RRP", "FINISH") or any(up.startswith(w) for w in SECTION_WORDS):
                continue
            name_parts.append(t)
        name_line = " ".join(name_parts).strip()

        # nearest heading above in the same column band
        heading = None
        best_dy = 1e9
        for h in headings:
            if h["y"] >= y:
                continue
            dy = y - h["y"]
            if dy > 400:  # too far — different product box
                continue
            # column overlap
            if abs(h["x0"] - x0) < 90 and dy < best_dy:
                best_dy = dy
                heading = h["text"].strip()
        # skip section-banner headings
        if heading and heading.upper() in SECTION_WORDS:
            heading = None

        # dims: nearest above in same column
        dims = None
        best = 1e9
        for dx0, dy, dm in dims_by_col:
            if dy < y and abs(dx0 - x0) < 120 and (y - dy) < best:
                best = y - dy
                dims = dm

        # name cell must describe a product (not a price/code/dimension junk cell)
        if name_line and JUNK_NAME.match(name_line):
            name_line = ""
        if not name_line and not heading:
            continue  # no usable name — skip this row entirely

        # finish variant = colour/finish name cell under a heading
        is_finish = bool(name_line) and bool(FINISH_HINT.match(name_line))
        products.append({
            "page": pno, "heading": heading, "name_line": name_line,
            "code": code, "price": price, "dims": dims, "is_finish": is_finish,
            "x0": x0, "y": y,
        })
    return products


def main():
    doc = fitz.open(PDF)
    all_rows = []
    for pno in range(doc.page_count):
        for r in parse_page(doc, pno):
            all_rows.append(r)
    doc.close()

    products, seen = [], set()
    for r in all_rows:
        if r["is_finish"]:
            name = f"{r['heading'] or ''} {r['name_line']}".strip()
        else:
            name = r["heading"] or r["name_line"]
        name = re.sub(r"\s+", " ", name).strip()
        if not name or len(name) < 4:
            continue
        sku = r["code"]
        if sku in seen:
            continue
        seen.add(sku)
        if EXCLUDE_RE.search(name):
            continue
        products.append({
            "page": r["page"],
            "name": name.title() if name.isupper() else name,
            "sku": sku,
            "price_gbp": r["price"],
            "price_note": "RRP",
            "dims": r["dims"] or {"width_mm": None, "depth_mm": None, "height_mm": None},
            "hand": None, "size_raw": "", "category": None, "image": None,
        })

    # classify by name
    for p in products:
        nm = p["name"].lower()
        if re.search(r"basin|sink|pedestal", nm): p["category"] = "basins"
        elif re.search(r"toilet|\bpan\b|cistern|\bwc\b|bidet", nm): p["category"] = "toilets"
        elif re.search(r"\bbath\b|bathtub|slipper", nm): p["category"] = "baths"
        elif re.search(r"walk[- ]?in|glass panel|fluted|shower panel|wetroom|wet room|\bframe\b", nm):
            p["category"] = "showering/shower-screens"
        elif re.search(r"enclosure|quadrant", nm): p["category"] = "showering/shower-enclosures"
        elif re.search(r"\btray\b|\btrays\b", nm): p["category"] = "showering/shower-trays"
        elif re.search(r"screen", nm): p["category"] = "showering/shower-screens"
        elif re.search(r"valve|shower kit|handset|shower head|\barm\b|support bar|diverter", nm):
            p["category"] = "showering"
        elif re.search(r"\btap\b|\btaps\b|mixer|monobloc", nm): p["category"] = "taps"
        elif re.search(r"mirror", nm): p["category"] = "mirrors-cabinets/mirrors"
        elif re.search(r"radiator|towel", nm): p["category"] = "heating/towel-rails"
        elif re.search(r"wall panel|end panel|cupboard|cabinet|vanity|\bunit\b|worktop|"
                       r"furniture|door|drawer|plinth|storage|handle", nm):
            p["category"] = "furniture"
        elif re.search(r"shelf|hook|ring|rail|holder|basket", nm): p["category"] = "accessories"
        else: p["category"] = "q4/uncategorised"

    # orphan finish-only names (no heading found) carry no product info — drop
    before = len(products)
    products = [p for p in products if not (FINISH_HINT.match(p["name"]) and len(p["name"].split()) <= 4)]
    # drop anything still named like junk
    products = [p for p in products if not JUNK_NAME.match(p["name"]) and len(p["name"]) >= 4]

    # multi-word colour/finish combos without a heading are also orphans
    COLOURS = r"(gloss|matt?e|super|soft|dove|carbon|henley|boston|cashmere|indigo|khaki|" \
              r"olive|espresso|tobacco|sandy|natural|satin|le?vanto|carrera|tuscany|fjord|" \
              r"graphite|anthracite|white|grey|gray|blue|black|green|beige|oak|walnut|" \
              r"brushed|chrome|brass|bronze|stone|slate|rimless|mm\b|\d+)"
    def _pure_finish(name):
        words = re.findall(r"[a-z0-9]+", name.lower())
        return bool(words) and all(re.fullmatch(COLOURS, w) for w in words)
    products = [p for p in products if not _pure_finish(p["name"])]

    # prose / marketing garbage + bare one-word range names carry no spec info
    PROSE = re.compile(r"availability|great service|noise reduction|next|delivery|"
                       r"guarantee|year|every|everything|design|britain|servicing", re.I)
    products = [p for p in products if not PROSE.search(p["name"])]
    products = [p for p in products if len(p["name"].split()) >= 2]

    out = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\q4-bathrooms\q4_rows.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=1)
    from collections import Counter
    print(f"{len(products)} products (from {len(all_rows)} rows) -> {out}")
    print("categories:", dict(Counter(p["category"] for p in products)))
    for p in products[:12]:
        print(f"  p{p['page']:3d} {p['sku']:10s} £{p['price_gbp']:7.0f} {str(p['dims'])[:34]:34s} {p['name'][:42]}")


if __name__ == "__main__":
    main()
