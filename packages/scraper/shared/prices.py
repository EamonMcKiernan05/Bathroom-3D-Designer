"""Price parsing — UK retail formats (doc 02 §1 schema: price_gbp, price_note, price_is_from).

Handles (verified against Ideal Bathrooms live pages):
  "£240.00 Inc VAT"                          flat
  "&pound; 240.00 Inc VAT"                   HTML entity
  "£<span itemprop=\"price\">140.00</span>"  microdata (number in a span)
  'itemprop="price" content="140.00"'        microdata attribute form
  "From £X" / "RRP £X" / "£X ex VAT"
"""
from __future__ import annotations

import re

# £1,234.56 / £240.00 / &pound; 240.00 / £240 / from £240
_PRICE = re.compile(r"(?P<from>from\s+|rrp\s+|was\s+)?[£€]\s*(?P<amt>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", re.I)
_ITEMPROP_ATTR = re.compile(r'itemprop="price"\s+content="(?P<amt>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"', re.I)
_ITEMPROP_TEXT = re.compile(r'itemprop=["\']price["\'][^>]*>\s*(?P<amt>\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', re.I)
_EX_VAT = re.compile(r"\bex\s*vat\b", re.I)
_INC_VAT = re.compile(r"\binc(?:luding)?\s*vat\b", re.I)
_FROM = re.compile(r"^\s*from\b", re.I)
_RRP = re.compile(r"^\s*rrp\b", re.I)


def _amount(text: str) -> float | None:
    for pat in (_ITEMPROP_ATTR, _ITEMPROP_TEXT):
        m = pat.search(text)
        if m:
            return float(m.group("amt").replace(",", ""))
    # strip tags so "£<span>140</span>" -> "£ 140" then match
    stripped = re.sub(r"<[^>]+>", " ", text)
    m = _PRICE.search(stripped)
    if m:
        return float(m.group("amt").replace(",", ""))
    return None


def parse_price(text: str | None) -> dict:
    """Parse a price fragment.

    Returns {price_gbp, price_note, price_is_from} (price None when absent).
    """
    if not text:
        return {"price_gbp": None, "price_note": None, "price_is_from": False}

    amt = _amount(text)
    if amt is None:
        return {"price_gbp": None, "price_note": None, "price_is_from": False}

    price_note = None
    if _EX_VAT.search(text):
        price_note = "ex VAT"
    elif _INC_VAT.search(text):
        price_note = "inc VAT"
    if _FROM.search(text) or re.search(r"\bfrom\s+£", text, re.I) or re.search(r"\bfrom\s+&pound;", text, re.I):
        price_note = "From"
    elif _RRP.search(text) or re.search(r"\brrp\b", text, re.I):
        price_note = "RRP"

    return {
        "price_gbp": round(amt, 2),
        "price_note": price_note,
        "price_is_from": bool(re.search(r"\bfrom\s+[£€&pound;]", text, re.I)),
    }