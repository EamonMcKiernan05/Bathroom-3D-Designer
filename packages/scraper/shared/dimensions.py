"""Dimension parsing (doc 02 §3.3 + Final Review #8).

Strategy: per-retailer extractors FIRST (they know the site's spec format),
then the generic regexes. Every result carries `dimensions_confidence`:
  high   — explicit per-field dimensions from structured specs
  medium — a single "W x H x D" pattern or named fields in free text
  low    — inferred/partial (e.g. only width found, or 2D pattern used)
  None   — nothing found
"""
from __future__ import annotations

import re

# --- generic patterns (doc 02 §3.3) -------------------------------------
_WDH = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm", re.I)
_NAMED = {
    "width": re.compile(r"(?:width|w)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm|cm)?", re.I),
    "height": re.compile(r"(?:height|h)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm|cm)?", re.I),
    "depth": re.compile(r"(?:depth|d|projection)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm|cm)?", re.I),
    "diameter": re.compile(r"(?:diameter|dia|⌀)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*(?:mm|cm)?", re.I),
}
_TWO_DIM = re.compile(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*mm", re.I)
_CM = re.compile(r"(\d+(?:\.\d+)?)\s*cm\b", re.I)

# "380mm (Width) 670mm (Depth) 790mm (Height)" — Ideal Bathrooms format
_PAREN_LABEL = re.compile(
    r"(\d+(?:\.\d+)?)\s*mm\s*\(\s*(width|w|depth|d|height|h|dia|diameter)\s*\)", re.I
)


def _to_mm(value: float, unit: str) -> float:
    return round(value * 10.0, 1) if unit == "cm" else round(value, 1)


def parse_ideal_bathrooms(text: str) -> dict:
    """'380mm (Width) 670mm (Depth) 790mm (Height)' — labelled pairs."""
    out = {"width_mm": None, "height_mm": None, "depth_mm": None, "diameter_mm": None}
    hits = 0
    for m in _PAREN_LABEL.finditer(text):
        val = float(m.group(1))
        label = m.group(2).lower()
        if label in ("width", "w"):
            out["width_mm"] = val
        elif label in ("height", "h"):
            out["height_mm"] = val
        elif label in ("depth", "d"):
            out["depth_mm"] = val
        elif label in ("dia", "diameter"):
            out["diameter_mm"] = val
        hits += 1
    confidence = "high" if hits >= 2 else ("medium" if hits == 1 else None)
    return out, confidence


def parse_dimensions(text: str) -> dict:
    """Generic parser. Returns {width_mm, height_mm, depth_mm, diameter_mm, confidence}."""
    if not text:
        return {"width_mm": None, "height_mm": None, "depth_mm": None, "diameter_mm": None, "confidence": None}

    result = {"width_mm": None, "height_mm": None, "depth_mm": None, "diameter_mm": None}

    def _mm(v: str) -> float:
        f = float(v)
        return round(f * 10.0, 1) if "cm" in v.lower() else round(f, 1)

    # W x H x D mm
    m = _WDH.search(text)
    if m:
        result["width_mm"] = _mm(m.group(1))
        result["height_mm"] = _mm(m.group(2))
        result["depth_mm"] = _mm(m.group(3))
        return {**result, "confidence": "medium"}

    # named fields
    named_hits = 0
    for key, pat in _NAMED.items():
        m = pat.search(text)
        if m:
            unit = "cm" if m.group(0).lower().endswith("cm") or "cm" in text[m.start():m.end()].lower() else "mm"
            result[key] = _to_mm(float(m.group(1)), unit)
            named_hits += 1

    # 2D W x H (panels/screens) — no depth
    if not result["width_mm"] and not result["height_mm"]:
        m = _TWO_DIM.search(text)
        if m:
            result["width_mm"] = float(m.group(1))
            result["height_mm"] = float(m.group(2))
            named_hits += 2

    if named_hits >= 3:
        return {**result, "confidence": "medium"}
    if named_hits >= 1:
        return {**result, "confidence": "low"}
    return {**result, "confidence": None}


def extract_dimensions(text: str, vendor: str | None = None) -> dict:
    """Full extractor: per-vendor first, then generic. Always sets confidence.

    Returns {width_mm, height_mm, depth_mm, diameter_mm, confidence}.
    """
    if not text:
        return {"width_mm": None, "height_mm": None, "depth_mm": None, "diameter_mm": None, "confidence": None}

    if vendor == "ideal-bathrooms":
        parsed, conf = parse_ideal_bathrooms(text)
        if conf:
            return {**parsed, "confidence": conf}

    generic = parse_dimensions(text)
    return generic
