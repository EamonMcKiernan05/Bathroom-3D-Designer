"""Parse Coram Showers brochure (31pp) spec tables into rows JSON.

Every product row is a horizontal band: dimension cells + prices + a product
code. Strategy: gather ALL spans with (x,y); group by y-row; a "product row"
is any y-row whose joined text contains a product code (letters+digits) AND a
price. Dimensions = the first two 3-4 digit numbers on that row (width,height).
Range heading = nearest large-font line above the row on the same page.
"""
import fitz
import json
import os
import re

PDF = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\coram-showers\coram-showers-brochure-april-2025_digital.pdf"

CODE_RE = re.compile(r"\b([A-Z][A-Z0-9]{5,15})\b")
PRICE_RE = re.compile(r"£\s*([\d,]+\.\d{2})")
NUM_RE = re.compile(r"\b(\d{3,4})\b")
HEADING_MIN_SIZE = 11


def _is_code(tok: str) -> bool:
    return bool(re.search(r"\d", tok)) and bool(re.search(r"[A-Z]", tok))


def spans(doc, pno):
    out = []
    for b in doc[pno].get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            if not l["spans"]:
                continue
            txt = "".join(s["text"] for s in l["spans"]).strip()
            if not txt:
                continue
            out.append({
                "x0": l["bbox"][0], "y": l["bbox"][1],
                "size": max(s["size"] for s in l["spans"]),
                "text": txt,
            })
    return out


def parse_page(doc, pno):
    ss = spans(doc, pno)
    if not ss:
        return []
    txt = doc[pno].get_text("text")
    if not PRICE_RE.search(txt):
        return []

    # headings (large font) sorted by y for range-name lookup
    heads = sorted([s for s in ss if s["size"] >= HEADING_MIN_SIZE and not s["text"].isdigit()],
                   key=lambda s: s["y"])

    # group by y row
    rows = {}
    for s in ss:
        key = round(s["y"] / 3) * 3
        rows.setdefault(key, []).append(s)

    products = []
    for y in sorted(rows):
        cells = sorted(rows[y], key=lambda c: c["x0"])
        line = " ".join(c["text"] for c in cells)
        code_m = None
        for tok in re.findall(r"\b[A-Z][A-Z0-9]{5,15}\b", line):
            if _is_code(tok):
                code_m = tok
                break
        if not code_m:
            continue
        prices = PRICE_RE.findall(line)
        nums = NUM_RE.findall(line)
        width = int(nums[0]) if nums else None
        height = int(nums[1]) if len(nums) > 1 else None
        # prefer the inc-VAT price (last one), else any
        price = float(prices[-1].replace(",", "")) if prices else None
        if price is None and not width:
            continue
        # nearest heading above
        range_name = None
        for h in heads:
            if h["y"] < y:
                t = h["text"].strip()
                if t.lower() not in ("sizes, codes and prices", "configurations") and len(t) > 2:
                    range_name = t
        products.append({
            "page": pno, "range": range_name, "code": code_m,
            "width": width, "height": height, "price_inc": price,
        })
    return products


def main():
    doc = fitz.open(PDF)
    all_rows = []
    for pno in range(doc.page_count):
        all_rows.extend(parse_page(doc, pno))
    doc.close()

    seen, products = set(), []
    for r in all_rows:
        if r["code"] in seen:
            continue
        seen.add(r["code"])
        rng = re.sub(r"\s+", " ", r["range"] or "Coram").strip()
        size = ""
        if r["width"]:
            size = f"{r['width']}" + (f"x{r['height']}" if r["height"] else "") + "mm"
        products.append({
            "page": r["page"],
            "name": f"{rng} {size}".strip(),
            "sku": f"CORAM-{r['code']}",
            "price_gbp": r["price_inc"],
            "price_note": "inc VAT",
            "dims": {"width_mm": r["width"], "height_mm": r["height"], "depth_mm": None},
            "hand": None, "size_raw": size,
            "category": "showering/shower-screens",
            "image": None,
        })

    out = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\coram-showers\coram_rows.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=1)
    print(f"{len(products)} products (from {len(all_rows)} rows) -> {out}")
    for p in products[:12]:
        print(f"  p{p['page']:3d} {p['sku']:20s} £{str(p['price_gbp']):9s} {p['name'][:44]}")


if __name__ == "__main__":
    main()
