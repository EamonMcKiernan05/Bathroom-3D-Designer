"""MyLife Bathrooms (https://mylifebathrooms.com/) — full-site scrape.

Magento 2, but product pages AND category tiles are fully SERVER-SIDE
rendered (verified 2026-08-05) — the old "needs Playwright" assumption was
wrong; no browser is required.

Strategy:
1. Build a URL -> category map by crawling the site's own subcategory pages
   (enumerated from sitemap.xml, verified 2026-08-05) with ?p=N pagination.
   Real category pages are crawled first; finish/colour filter pages only
   fill gaps.
2. Enumerate ALL products from sitemap.xml (depth-1 URLs, ~2,200 entries)
   and fetch each product page directly (og:type=product guards).
3. Attribution: brand = "MyLife"; the catalogue card shows the retailer
   (mylife) as supplier. Category comes from step 1 (fallback
   mylife/uncategorised).

Images come from the mage/gallery/gallery JSON (positions + captions, no
cross-sell noise). Prices from data-price-amount + the "From" price-label.
Dimensions are parsed from the description ONLY (full-page regexes match
CSS/JS pixel values like `width: 415px` and produce garbage dims).
"""
from __future__ import annotations

import html as htmlmod
import json
import re

from ..shared.dimensions import extract_dimensions
from ..shared.prices import parse_price
from .base import VendorScraper

BASE = "https://mylifebathrooms.com"

# Sitemap depth-1 segments that are NOT products (info/news/tag pages).
_RESERVED = {
    "news", "about-us", "privacypolicy", "return-refund-policy", "warranty-terms",
    "returns", "general-customer-terms", "become-a-retailer", "product-registration",
    "service-engineer-report", "service-call-request", "general-supplier-terms",
    "careers", "brochures", "site-map", "find-a-retailer", "contact", "product-tag",
    "how-to-videos", "discontinued-product-search", "collection", "3d-configurator",
    "where-to-buy", "search", "customer", "wishlist", "catalogsearch",
    # top-level CATEGORY landing pages are also depth-1 sitemap URLs
    "furniture", "mirrors-cabinets", "ceramics", "bathing", "showering",
    "heated-towel-rails", "taps-accessories", "basins", "accessories",
    "fitted-furniture", "taps",
}

# mylife subcategory path (no leading/trailing slash) -> normalized taxonomy
# slug. Reuses the shared taxonomy where it exists; new leaves otherwise.
_PATH_TO_SLUG = {
    # furniture
    "furniture": "furniture",
    "furniture/contemporary": "furniture",
    "furniture/traditional": "furniture",
    "furniture/contemporary/floorstanding": "furniture/floorstanding",
    "furniture/traditional/floorstanding": "furniture/floorstanding",
    "furniture/contemporary/wallmounted": "furniture/wall-mounted",
    "furniture/traditional/wallmounted": "furniture/wall-mounted",
    "furniture/contemporary/furniture-with-worktops": "furniture/with-worktops",
    "furniture/traditional/furniture-with-worktops": "furniture/with-worktops",
    "furniture/contemporary/furniture-with-basins": "furniture/with-basins",
    "furniture/traditional/furniture-with-basins": "furniture/with-basins",
    "furniture/contemporary/cloakroom-units": "furniture/cloakroom-units",
    "furniture/contemporary/btw-units": "furniture/btw-units",
    "furniture/fitted": "furniture/fitted",
    "furniture/worktops": "furniture/worktops",
    "furniture/handles": "furniture/handles",
    "fitted-furniture": "furniture/fitted",
    # ceramics -> toilets
    "ceramics": "toilets",
    "ceramics/btw-wc": "toilets/back-to-wall",
    "ceramics/fully-enclosed-wc": "toilets/fully-enclosed",
    "ceramics/open-back-wc": "toilets/open-back",
    "ceramics/wall-hung-wc": "toilets/wall-hung",
    "ceramics/toilet-seats": "toilets/toilet-seats",
    "ceramics/flush-buttons": "toilets/flush-buttons",
    "ceramics/concealed-cisterns": "toilets/concealed-cisterns",
    "ceramics/douche-kits": "showering/douche-kits",
    # basins
    "basins": "basins",
    "basins/freestanding": "basins/freestanding",
    "basins/vanity-basins": "basins/vanity",
    "basins/semi-recessed": "basins/semi-recessed",
    "basins/fitted-furniture": "basins/fitted",
    "basins/cloakroom": "basins/cloakroom",
    # bathing -> baths
    "bathing": "baths",
    "bathing/contemporary": "baths",
    "bathing/traditional": "baths",
    "bathing/contemporary/freestanding-baths": "baths/freestanding",
    "bathing/traditional/freestanding-baths": "baths/freestanding",
    "bathing/contemporary/shower-baths": "baths/shower-bath",
    "bathing/bath-panels-screens": "baths/bath-panels-screens",
    # showering
    "showering": "showering",
    "showering/enclosures": "showering/shower-enclosures",
    "showering/trays": "showering/shower-trays",
    "showering/wetroom-panels": "showering/wetroom-panels",
    "showering/concealed": "showering/concealed-showers",
    "showering/exposed": "showering/exposed-showers",
    "showering/traditional": "showering/traditional-showers",
    "showering/components": "showering/components",
    "showering/wastes": "showering/wastes",
    "showering/finish": "showering",
    "showering/finish/black": "showering",
    "showering/finish/brushed-brass": "showering",
    "showering/finish/chrome": "showering",
    "showering/finish/gun-metal": "showering",
    # mirrors & cabinets
    "mirrors-cabinets": "mirrors-cabinets",
    "mirrors-cabinets/mirrors": "mirrors-cabinets/mirrors",
    "mirrors-cabinets/led-mirrors": "mirrors-cabinets/illuminated-mirrors",
    "mirrors-cabinets/mirrored-cabinets": "mirrors-cabinets/mirror-cabinets",
    # heated towel rails
    "heated-towel-rails": "heating/towel-rails",
    "heated-towel-rails/contemporary": "heating/towel-rails",
    "heated-towel-rails/contemporary/kallan": "heating/towel-rails",
    "heated-towel-rails/traditional": "heating/towel-rails",
    "heated-towel-rails/valves": "heating/towel-rail-valves",
    "heated-towel-rails/thermostatic-valves": "heating/towel-rail-valves",
    "heated-towel-rails/electric-elements-fuel-adaptors": "heating/towel-rail-elements",
    "heated-towel-rails/pipe-collar-kits": "heating/towel-rail-accessories",
    # taps
    "taps-accessories": "taps",
    "taps-accessories/basin-taps": "taps/basin-taps",
    "taps-accessories/basin-taps/deck-mounted": "taps/basin-taps",
    "taps-accessories/basin-taps/wall-mounted": "taps/basin-taps",
    "taps-accessories/bath-taps": "taps/bath-taps",
    "taps-accessories/bath-taps/deck-mounted": "taps/bath-taps",
    "taps-accessories/bath-taps/floor-mounted": "taps/bath-taps",
    "taps-accessories/bath-taps/wall-mounted": "taps/bath-taps",
    "taps-accessories/bath-wastes": "taps/bath-wastes",
    "taps-accessories/bottle-traps": "taps/bottle-traps",
    "taps-accessories/douche-kits": "showering/douche-kits",
    "taps-accessories/overflow-rings": "taps/overflow-rings",
    "taps-accessories/finish": "taps",
    "taps/finish/black": "taps",
    "taps/finish/brushed-brass": "taps",
    "taps/finish/chrome": "taps",
    "taps/finish/gun-metal": "taps",
    # accessories (finish-filtered pages; no unfiltered root in the sitemap)
    "accessories": "accessories",
    "accessories/black": "accessories",
    "accessories/brushed-brass": "accessories",
    "accessories/chrome": "accessories",
    "accessories/gun-metal": "accessories",
    "accessories/stainless-steel": "accessories",
}

# identity map so map_category() returns the normalized slug verbatim
CATEGORY_MAP = {slug: slug for slug in set(_PATH_TO_SLUG.values())}
CATEGORY_MAP["all"] = "mylife/uncategorised"
CATEGORY_MAP["uncategorised"] = "mylife/uncategorised"

# finish/colour filter pages — crawled SECOND, only filling gaps
_FILTER_PATH_RE = re.compile(
    r"(?:^|/)finish(?:/|$)|^accessories/(?:black|brushed-brass|chrome|gun-metal|stainless-steel)$"
)

_TILE = re.compile(
    r'<a[^>]*class="[^"]*product-item-link[^"]*"[^>]*href="([^"]+)"'
    r'|<a[^>]*href="([^"]+)"[^>]*class="[^"]*product-item-link',
    re.I,
)
# hidden plumbing + small parts stay OUT of the 3D catalogue (user decision
# 2026-08-05) — they use generic models. Applied to the product name.
_EXCLUDE_RE = re.compile(
    r"\bwastes?\b|\boverflows?\b|\btraps?\b|\bpipework?\b|\bdrains?\b|"
    r"\btaps?\b|\bmixer\b|\bshelf\b|\bshelving\b|\bleg set\b|\bfixing kit\b",
    re.I,
)
_SKU = re.compile(r"catalog_product_view_sku_([A-Za-z0-9][A-Za-z0-9._\-]*)")
_TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.I | re.S)
_H1 = re.compile(r'<h1[^>]*class="[^"]*page-title[^"]*"[^>]*>\s*(?:<span[^>]*>)?\s*([^<]+)', re.I | re.S)
_DESC = re.compile(
    r'itemprop="description"[^>]*>(.*?)(?:</div>\s*<div class="product attribute|</div>\s*</div>)',
    re.I | re.S,
)
_GALLERY_SCRIPT = re.compile(r'<script type="text/x-magento-init">(.*?)</script>', re.I | re.S)
_PRICE_AMOUNT = re.compile(r'data-price-amount="([\d.]+)"')


def _norm(url: str) -> str:
    """Canonical product URL key for the category map."""
    return url.split("?", 1)[0].rstrip("/")


class MyLifeScraper(VendorScraper):
    slug = "mylife"
    base_url = BASE
    # single pseudo-category: the sitemap enumerates every product page
    start_categories = [("all", "/sitemap.xml")]
    CATEGORY_MAP = CATEGORY_MAP

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._url_category: dict[str, str] | None = None  # built lazily

    # -- category map ------------------------------------------------------
    _MAP_CACHE = None  # set in __init__ (needs instance)

    def _map_cache_path(self):
        import pathlib

        d = pathlib.Path(__file__).resolve().parent.parent / "cache"
        d.mkdir(parents=True, exist_ok=True)
        return d / "mylife_url_category.json"

    def _build_category_map(self):
        """Crawl mylife subcategory pages (SSR tiles) -> URL->category slug.
        Cached to packages/scraper/cache/mylife_url_category.json; delete the
        file to force a rebuild."""
        import logging
        log = logging.getLogger("scraper.vendor")
        if self._url_category is not None:
            return
        cache = self._map_cache_path()
        if cache.exists():
            try:
                self._url_category = json.loads(cache.read_text(encoding="utf-8"))
                log.info("[mylife] category map loaded from cache (%d URLs)", len(self._url_category))
                return
            except (ValueError, OSError):
                pass
        self._url_category = {}
        html = self.http.fetch_html(self.base_url + "/sitemap.xml")
        if not html:
            log.warning("[mylife] sitemap fetch failed — categories will fall back")
            return
        prefix = self.base_url + "/"
        paths = []
        for u in re.findall(r"<loc>([^<]+)</loc>", html):
            if not u.startswith(prefix):
                continue
            p = u[len(prefix):].strip("/")
            parts = p.split("/")
            if len(parts) >= 2 and parts[0] in {
                "furniture", "mirrors-cabinets", "ceramics", "bathing", "showering",
                "heated-towel-rails", "taps-accessories", "basins", "accessories",
                "fitted-furniture", "taps",
            }:
                paths.append(p)
        # real categories first, finish/colour filter pages second
        real = [p for p in sorted(paths) if not _FILTER_PATH_RE.search(p)]
        filt = [p for p in sorted(paths) if _FILTER_PATH_RE.search(p)]
        log.info("[mylife] building category map: %d categories + %d filter pages", len(real), len(filt))
        for pass_paths in (real, filt):
            for p in pass_paths:
                slug = _PATH_TO_SLUG.get(p)
                if slug:
                    self._crawl_category_pages(p, slug)
        try:
            cache.write_text(json.dumps(self._url_category), encoding="utf-8")
            log.info("[mylife] category map cached (%d URLs)", len(self._url_category))
        except OSError as e:
            log.warning("[mylife] could not write category map cache: %s", e)

    def _crawl_category_pages(self, path: str, slug: str):
        """Follow ?p=N pagination collecting product tile URLs for `path`."""
        url = f"{self.base_url}/{path}/"
        seen_pages: set[str] = set()
        for page in range(1, 30):
            page_url = url if page == 1 else f"{url}?p={page}"
            if page_url in seen_pages:
                break
            seen_pages.add(page_url)
            html = self.http.fetch_html(page_url)
            if not html:
                break
            tiles = [m.group(1) or m.group(2) for m in _TILE.finditer(html)]
            if not tiles:
                break
            for t in tiles:
                # filter pages run second and only fill gaps
                self._url_category.setdefault(_norm(t), slug)
            # stop when the next page link no longer exists on the page
            if f"?p={page + 1}" not in html:
                break

    # -- sitemap -> product URLs -------------------------------------------
    def list_product_urls(self, html: str, category_url: str) -> list[str]:
        self._build_category_map()
        prefix = self.base_url + "/"
        urls = []
        seen = set()
        for u in re.findall(r"<loc>([^<]+)</loc>", html):
            if not u.startswith(prefix):
                continue
            p = u[len(prefix):].strip("/")
            parts = p.split("/")
            if len(parts) != 1:
                continue
            seg = parts[0]
            if seg in _RESERVED or not re.match(r"^[a-z0-9][a-z0-9\-]*$", seg):
                continue
            if u not in seen:
                seen.add(u)
                urls.append(u)
        return urls

    # -- product page -------------------------------------------------------
    def extract_product(self, html: str, url: str) -> dict | None:
        # strict guard: sitemap depth-1 URLs should all be products, but
        # soft-404s and retired pages must not become catalogue rows
        if 'property="og:type" content="product"' not in html:
            return None

        name = None
        m = _H1.search(html)
        if m:
            name = htmlmod.unescape(m.group(1)).strip()
        if not name:
            m = _TITLE.search(html)
            name = htmlmod.unescape(m.group(1)).split("|")[0].strip() if m else None
        if not name:
            return None

        # small parts / hidden plumbing are out of scope (generic models)
        if _EXCLUDE_RE.search(name):
            return None

        sku = None
        m = _SKU.search(html)
        if m:
            sku = m.group(1)
        if not sku:
            sku = _norm(url).rsplit("/", 1)[-1]

        # price — first data-price-amount is the product's own price; option
        # prices for configurable products come later on the page
        price = {"price_gbp": None, "price_note": None, "price_is_from": False}
        m = _PRICE_AMOUNT.search(html)
        if m:
            window = html[max(0, m.start() - 400):m.end() + 50]
            price = parse_price(window)
            price["price_gbp"] = round(float(m.group(1)), 2)
            if re.search(r'price-label">\s*From\s*<', window, re.I):
                price["price_note"] = "From"
                price["price_is_from"] = True

        # description
        description = None
        m = _DESC.search(html)
        if m:
            txt = re.sub(r"<[^>]+>", " ", m.group(1))
            txt = re.sub(r"\s+", " ", htmlmod.unescape(txt)).strip()
            description = txt[:2000] or None

        # dimensions — from description ONLY (full-page regexes match CSS
        # pixel values like `width: 415px` and produce garbage dims; mylife
        # spec sheets live in brochure PDFs, not product pages)
        dims = extract_dimensions(description or "", vendor=None)
        confidence = dims.pop("confidence")

        # gallery images — the full mage/gallery/gallery JSON (positions +
        # captions, no cross-sell noise)
        imgs = []
        for sm in _GALLERY_SCRIPT.finditer(html):
            if "mage/gallery/gallery" not in sm.group(1):
                continue
            try:
                init = json.loads(sm.group(1))
                data = (
                    init.get("[data-gallery-role=gallery-placeholder]", {})
                    .get("mage/gallery/gallery", {})
                    .get("data", [])
                )
                data = [d for d in data if d.get("type") == "image"]
                data.sort(key=lambda d: int(d.get("position") or 0))
                seen_fn = set()
                for item in data:
                    u = item.get("full") or item.get("img")
                    if not u:
                        continue
                    fn = u.rsplit("/", 1)[-1]
                    if fn in seen_fn:
                        continue
                    seen_fn.add(fn)
                    imgs.append(u)
            except (ValueError, KeyError, TypeError):
                pass
            break
        if not imgs:
            og = re.search(r'property="og:image" content="([^"]+)"', html)
            if og:
                imgs = [og.group(1)]

        category_key = (self._url_category or {}).get(_norm(url)) or "uncategorised"

        return {
            "retailer_sku": sku,
            "retailer_url": url,
            "name": name,
            "brand": "MyLife",
            "description": description,
            "price_gbp": price["price_gbp"],
            "price_note": price["price_note"],
            "price_is_from": price["price_is_from"],
            **dims,
            "dimensions_confidence": confidence,
            "finishes": [],
            "colours": [],
            "sizes": [],
            "image_urls": imgs[:3],
            "in_stock": None,
            "category_key": category_key,
        }
