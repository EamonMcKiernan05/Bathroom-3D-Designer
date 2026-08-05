"""Per-vendor scraper registry (doc 02 §1 architecture diagram).

One class per retailer; a site breaking never blocks the others.
Priority order (Phase 6.2): ideal-bathrooms → genesis → mylife →
crosswater → warren-keys (manual curation) → city-plumbing (last).
"""
from .base import VendorScraper

REGISTRY: dict[str, type[VendorScraper]] = {}


def register(cls: type[VendorScraper]) -> type[VendorScraper]:
    REGISTRY[cls.slug] = cls
    return cls


def get_scraper(slug: str) -> type[VendorScraper]:
    if slug not in REGISTRY:
        raise KeyError(f"Unknown retailer slug '{slug}'. Known: {sorted(REGISTRY)}")
    return REGISTRY[slug]


PRIORITY_ORDER = [
    "ideal-bathrooms",
    "genesis",
    "mylife",
    "crosswater",
    "warren-keys",
    "city-plumbing",
]

# Import vendors so they self-register.
from . import (  # noqa: E402,F401
    city_plumbing,
    crosswater,
    eastbrook,
    genesis,
    ideal_bathrooms,
    kaldewei,
    mylife,
    tissino,
    warren_keys,
)

# Register each vendor class.
for _cls in (
    ideal_bathrooms.IdealBathroomsScraper,
    genesis.GenesisScraper,
    mylife.MyLifeScraper,
    crosswater.CrosswaterScraper,
    eastbrook.EastbrookScraper,
    kaldewei.KaldeweiScraper,
    tissino.TissinoScraper,
    warren_keys.WarrenKeysLoader,
    city_plumbing.CityPlumbingScraper,
):
    register(_cls)
