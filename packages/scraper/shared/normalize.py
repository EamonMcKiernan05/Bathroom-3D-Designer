"""Finish/colour normalization → canonical slugs used across the catalogue.

Canonical finishes (materials library in packages/model-gen/materials + seed):
chrome, matt_black, brushed_brass, brushed_nickel, white, anthracite, oak,
polished_nickel, gunmetal, satin_brass, black.
"""
from __future__ import annotations

import re

FINISH_ALIASES = {
    "chrome": ["chrome", "polished chrome", "chromium"],
    "matt_black": ["matt black", "matte black", "mat black", "black"],
    "brushed_brass": ["brushed brass", "satin brass", "brass"],
    "brushed_nickel": ["brushed nickel", "satin nickel", "polished nickel", "nickel"],
    "white": ["white", "gloss white", "matt white", "matte white"],
    "anthracite": ["anthracite", "graphite", "charcoal"],
    "oak": ["oak", "natural oak", "oak effect"],
    "gunmetal": ["gunmetal", "gun metal"],
    "black": ["black", "gloss black", "matt black"],
}

COLOUR_ALIASES = {
    "white": ["white", "gloss white"],
    "black": ["black", "matt black"],
    "grey": ["grey", "gray", "anthracite"],
    "beige": ["beige", "cream", "ivory", "bone"],
    "oak": ["oak", "wood"],
}


def normalize_finish(value: str | None) -> str | None:
    """Map a raw finish string to a canonical slug, or None."""
    if not value:
        return None
    v = value.strip().lower()
    for canonical, aliases in FINISH_ALIASES.items():
        if v == canonical or any(v == a or v in a or a in v for a in aliases):
            return canonical
    return None


def normalize_colour(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    for canonical, aliases in COLOUR_ALIASES.items():
        if v == canonical or any(v == a or a in v for a in aliases):
            return canonical
    return v
