"""Parse Scudo Edition Twenty Two price list (231pp) into rows JSON.

Layout (verified p15):
- product heading block(s): "MIDDLETON RIMLESS CLOSED BACK PAN" +
  "INCLUDING CISTERN & SOFT CLOSE SEAT"
- dims line: "360w x 780h x 590d"
- table header: "Description Price Inc VAT Code"
- rows: description line(s), "£295.00 MIDDLETON-" + continuation "CLOSEPAN"
  (code may wrap across lines with a trailing hyphen)

Codes are UPPER-HYPHEN tokens like MIDDLETON-CLOSEPAN, CERAMIC-CISTERN-444.
"""
import fitz
import json
import os
import re
import sys

PDF = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\scudo\Scudo-Edition-Twenty-Two-UK-LR-Spreads.pdf"
OUT_DIR = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\scudo\extracted"
os.makedirs(OUT_DIR, exist_ok=True)

DIMS_RE = re.compile(r"(\d{3,4})\s*w\s*x\s*(\d{3,4})\s*h\s*x\s*(\d{3,4})\s*d", re.I)
PRICE_RE = re.compile(r"£\s*([\d,]+(?:\.\d{2})?)")
CODE_TAIL_RE = re.compile(r"£\s*[\d,]+(?:\.\d{2})?\s*([A-Z][A-Z0-9\-]*)\s*$")
CODE_LINE_RE = re.compile(r"^[A-Z][A-Z0-9\-]+$")
HEADER_RE = re.compile(r"^Description\s*$", re.I)
CAT_RULES = [
    (re.compile(r"pan|toilet|cistern|seat|bidet|wc\b|rimless", re.I), "toilets"),
    (re.compile(r"basin|pedestal|bottle trap", re.I), "basins"),
    (re.compile(r"bath\b|shower bath", re.I), "baths"),
    (re.compile(r"shower|enclosure|door|panel|tray", re.I), "showering"),
    (re.compile(r"mirror|cabinet", re.I), "mirrors-cabinets/mirrors"),
    (re.compile(r"furniture|vanity|unit|worktop|handle", re.I), "furniture"),
    (re.compile(r"radiator|towel|heated", re.I), "heating/towel-rails"),
    (re.compile(r"tap|mixer", re.I), "taps"),
]

def categorize(text):
    for rx, cat in CAT_RULES:
        if rx.search(text):
            return cat
    return None


def parse_page(doc, pno, section):
    page = doc[pno]
    lines = [l.strip() for l in page.get_text("text").split("\n")]
    lines = [l for l in lines if l.strip()]

    products = []
    current = None  # heading context
    i = 0
    while i < len(lines):
        line = lines[i]
        # dims line -> new product heading context was the lines above it
        dm = DIMS_RE.search(line)
        if dm:
            # heading = up to 4 lines above dims
            head = []
            j = i - 1
            while j >= 0 and len(head) < 4:
                cand = lines[j]
                if PRICE_RE.search(cand) or CODE_LINE_RE.match(cand) or cand.lower() in ("description", "code", "price"):
                    break
                head.insert(0, cand)
                j -= 1
            name = " ".join(head).strip()
            name = re.sub(r"\s+", " ", name)
            if len(name) > 80:
                name = name[:80]
            current = {
                "name": name.title(),
                "dims": {"width_mm": int(dm.group(1)), "height_mm": int(dm.group(2)), "depth_mm": int(dm.group(3))},
                "header_seen": False,
            }
            i += 1
            continue
        # table header
        if current is not None and HEADER_RE.match(line):
            current["header_seen"] = True
            i += 1
            continue
        # price row
        pm = PRICE_RE.search(line)
        if current is not None and current.get("header_seen") and pm:
            price = float(pm.group(1).replace(",", ""))
            # description: text before the £ on this line (may be empty when
            # the description sits on the previous line(s))
            desc = line[: pm.start()].strip()
            if not desc:
                # look at previous line if it's a plain description line
                k = i - 1
                if k >= 0 and not PRICE_RE.search(lines[k]) and not HEADER_RE.match(lines[k]) and not CODE_LINE_RE.match(lines[k]):
                    desc = lines[k].strip()
            # "Combined" rows are bundle totals, not products
            if re.match(r"combined", desc, re.I) or re.match(r"combined", line, re.I):
                i += 1
                continue
            # code: trailing token on the SAME line (toilets layout), or the
            # NEXT line(s) (furniture layout: "£672.00" then "BOTA-500FLUTED-
            # STONE", with hyphen continuation lines)
            tm = CODE_TAIL_RE.search(line)
            code = tm.group(1) if tm else None
            if not code and i + 1 < len(lines):
                nxt = lines[i + 1]
                if CODE_LINE_RE.match(nxt) and len(nxt) < 40:
                    code = nxt
                    i += 1
            if code is not None and code.endswith("-"):
                # continuation line(s)
                k = i + 1
                while k < len(lines) and CODE_LINE_RE.match(lines[k]) and len(lines[k]) < 30:
                    code += lines[k]
                    k += 1
                    i = k - 1
            if code and re.match(r"^[A-Z]", code) and any(c.isdigit() for c in code) or code and len(code) > 4:
                products.append({
                    "page": pno,
                    "name": current["name"],
                    "row_desc": re.sub(r"\s+", " ", desc).strip(),
                    "sku": code.strip("-"),
                    "price_gbp": price,
                    "dims": dict(current["dims"]),
                    "category": categorize(current["name"] + " " + desc),
                })
            i += 1
            continue
        i += 1
    return products


def main():
    doc = fitz.open(PDF)
    all_rows = []
    # crude section detection from TOC-like headers at top of page
    for pno in range(doc.page_count):
        try:
            rows = parse_page(doc, pno, None)
            all_rows.extend(rows)
        except Exception as e:
            print(f"page {pno} error: {e}", file=sys.stderr)
    doc.close()
    # dedupe
    seen, deduped = set(), []
    for r in all_rows:
        if r["sku"] in seen:
            continue
        seen.add(r["sku"])
        deduped.append(r)
    out = r"C:\Users\Eamon\Desktop\bathroom-3d\assets\brochures\scudo\scudo_pricelist_rows.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=1)
    from collections import Counter

    print(f"{len(deduped)} products (from {len(all_rows)} rows) -> {out}")
    print("categories:", dict(Counter(r["category"] for r in deduped)))
    for r in deduped[:12]:
        print(f"  p{r['page']:3d} {r['sku']:28s} £{r['price_gbp']:7.2f} {r['name'][:40]}")


if __name__ == "__main__":
    main()
