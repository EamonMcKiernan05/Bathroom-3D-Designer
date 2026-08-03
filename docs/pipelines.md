# Scraping & Model-Generation Pipelines

The Bathroom Designer project has two back-end content pipelines: a **polite web scraper** that ingests real products from Isle-of-Man & UK bathroom retailers, and a **parametric 3D model generator** that turns each scraped product's dimensions into a GLB model. Both are driven from the `packages/` directory and write into the shared `apps/api` PostgreSQL schema.

---

## 1. Scraping pipeline

`packages/scraper/` is organised as one **vendor module per retailer** under `vendors/`, sharing a common pipeline in `shared/`:

- `vendors/<retailer>.py` — each implements the `VendorScraper` contract: `slug`, `base_url`, `start_categories`, a `CATEGORY_MAP`, `list_product_urls()` and `extract_product()`. A site breaking never blocks the others.
- `vendors/base.py` — the shared **run loop**: it iterates the category URLs, discovers product URLs, fetches each product page, extracts a normalised product dict, and persists it (committing every 10 products so a crash doesn't lose the whole run). It also tracks per-run stats and opens/closes a `scrape_jobs` row.
- `shared/http.py` — `PoliteSession`: robots.txt respect, random 2–5 s delays, user-agent rotation, and retry/backoff on 403/429/503.
- `shared/dimensions.py` — dimension parsing with a **confidence score** (`high` / `medium` / `low` / `None`), cm→mm conversion, per-retailer extractors first then generic regexes.
- `shared/prices.py` — UK price parsing (£, *Inc/Ex VAT*, *From*/*RRP*, and microdata `itemprop=price`).
- `shared/images.py` — image download → resize → WebP + 256 px thumbnail (details below).
- `shared/db.py` — the shared DB pipeline: upsert products keyed on `(retailer_id, retailer_sku)`, get-or-create categories, replace product images, track `scrape_jobs`, and flag `model_status='pending'` when dimensions change.

Vendors register themselves in `vendors/__init__.py` and run in **priority order**:

```
ideal-bathrooms → genesis → mylife → crosswater → warren-keys → city-plumbing
```

### CLI usage

The scraper runs with the `apps/api` venv Python from the `packages/` directory via `python -m scraper.cli`. On Windows the venv interpreter is `apps/api/.venv/Scripts/python.exe`.

```bash
# List the registered retailers
python -m scraper.cli --list

# DRY-RUN: fetch + extract one retailer but write nothing to the DB
apps/api/.venv/Scripts/python.exe -m scraper.cli --retailer ideal-bathrooms --dry-run --limit 5

# Live run, capped at 20 products, only the toilets & vanity-units categories
python -m scraper.cli --retailer ideal-bathrooms --limit 20 --categories toilets,vanity-units

# Run every retailer in priority order
python -m scraper.cli --all

# Warren Keys is a manual-curation loader (no live crawl) — pass a curated file
python -m scraper.cli --retailer warren-keys --curated curated.json
```

Flags: `--retailer <slug>`, `--all`, `--list`, `--dry-run`, `--limit N`, `--categories a,b`, `--curated <path>`, `-v/--verbose`. A live (non-dry-run) run first calls `ensure_schema()` and requires the retailer to exist in `retailers` (run `app.seed` first).

### Vendors at a glance

| Retailer slug | Platform | Rendering | Notes |
|---|---|---|---|
| `ideal-bathrooms` | Custom CMS (3 Legs Ltd) | SSR | Priority 1; small catalogue; labelled dimensions give `high` confidence |
| `genesis` | WordPress + WooCommerce | SSR | Priority 2; tile edging / floor trims / shower channels subset; **prices often `null`** (variable products) |
| `mylife` | Magento 2 (Adobe Commerce) | **JS** (categories); SSR product pages | Priority 3; REST API is auth-gated (401), so browser path required |
| `crosswater` | Custom CMS | SSR product pages | Priority 4; **sitemap.xml drives URL discovery** (~870 products), no browser needed |
| `warren-keys` | Tile supplier (PDF brochures) | — | Priority 5; **manual curation loader** via `--curated` file, not a crawler |
| `city-plumbing` | React/Next.js | **JS** | **Last**; massive site scoped to bathroom categories only; conservative 5–7 s delays |

### Image pipeline

`shared/images.py` downloads each image and processes it in-memory with Pillow: converts to RGB, **resizes to ≤1200 px wide** (LANCZOS), saves as **WebP q85**, and produces a **256 px thumbnail**. Two files per source image are written:

- **Local dev** → `assets/products/<retailer_slug>/<sku>/img_NN.webp` (+ `img_NN_thumb.webp`), and the DB stores URL paths like `/products/<retailer_slug>/<sku>/img_00.webp`.
- **Production** → when `MINIO_ENDPOINT` is set, the same files upload to the MinIO/S3 bucket `bathroom-assets` instead, and object keys are returned.

The FastAPI app serves the local `assets/` tree directly — `main.py` mounts `/products`, `/models`, `/thumbnails`, and `/textures` as static directories (a stand-in for MinIO in dev).

---

## 2. Model generation pipeline

`packages/model-gen/` builds a **parametric 3D model** for each scraped product, **scaled to the real product dimensions** so the GLB matches the retailer's specs.

- `blender_lib.py` — parametric builders for **17 categories** (`toilet`, `basin`, `bath`, `shower-tray`, `shower-screen`, `shower-head`, `shower-set`, `radiator`, `towel-rail`, `mirror`, `cabinet`, `vanity-unit`, `tap`, `shelf`, `towel-ring`, `robe-hook`, `soap-dish`), a `FINISH_MATERIALS` map (chrome, brass, nickel, matt black, anthracite, oak, white…), and **`build_scaled()`**, which measures the *actual* built geometry's bounding box and scales it to the product's width/height/depth in mm (axes missing from the data are left at the generic size), then applies the product's finish override.
- `gen_one.py` — the **headless Blender entry point**: reads a product JSON spec, builds the scaled model, renders a 256 px EEVEE thumbnail, and outputs `assets/models/model_<id>.glb` + `assets/thumbnails/model_<id>.png`, printing `MODEL_OK <id>`.
- `batch_generate.py` — the **DB-driven driver** (runs in the `apps/api` venv). It queries `products` where `model_status='pending'` (and category is set), maps each category → builder slug, invokes Blender headless per product, and on success updates the row with `model_url=/models/model_<id>.glb`, `model_status='ready'`, `model_file_kb`, `model_polygons`, `thumbnail_url=/thumbnails/model_<id>.png`, and writes a `ModelJob` row. Failures set `model_status='failed'` and record a `ModelJob` with the error.
- `single_generate.py` — thin wrapper to generate one product by id.

Products default to `model_status='pending'`, so newly scraped products are queued for generation automatically; the seeded demo products are already `ready`. When a scrape detects that dimensions changed, `shared/db.py` re-flags the row `needs_model_update=True` / `model_status='pending'` so the model regenerates.

### CLI usage

```bash
# From packages/model-gen, with the apps/api venv active:
python batch_generate.py                 # all pending products
python batch_generate.py --dry-run       # list what would run
python batch_generate.py --retailer ideal-bathrooms
python batch_generate.py --category toilets
python batch_generate.py --product-id 1234

# Generate a single product
python single_generate.py --product-id 1234
```

The batch driver uses the Blender install at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` and times out individual builds at 120 s.

**Data flow:** scraped product dims (`width_mm` / `height_mm` / `depth_mm`, plus `dimensions_confidence`) → `batch_generate.py` → parametric GLB scaled to those exact dims → `model_url` set → served by FastAPI's `/models` static mount.

---

## 3. Admin API endpoints

`apps/api/app/routers/admin.py` exposes two read-only ops endpoints (mounted in `main.py` under the `/api/v1/admin` prefix):

- **`GET /api/v1/admin/scrape-status`** — most recent `ScrapeJob` per retailer (job type, status, found/new/updated/failed counts, timestamps, duration, errors) plus the list of currently-running job ids.
- **`GET /api/v1/admin/model-status`** — model generation queue: `status_counts` (pending/ready/failed per status), the latest pending products, and the 25 most recent `ModelJob` rows (method, status, output URL, polygon count, file size, error).

---

## 4. Robots.txt compliance & politeness

All HTTP goes through `PoliteSession` (`shared/http.py`), which:

- Fetches and honours **robots.txt** — URLs it disallows are skipped (with a log line), and the robots file is fetched through the same real-UA session so Cloudflare-style 403s don't produce a bypass.
- Throttles with a **random 2–5 s delay** between requests (configurable via `SCRAPER_MIN_DELAY` / `SCRAPER_MAX_DELAY`).
- Rotates real desktop **User-Agents** and retries with backoff on 403/429/503 (up to `SCRAPER_MAX_RETRIES`, default 3).
- Sends an **`X-Purpose: Product catalogue aggregation`** header for transparency.

City Plumbing deliberately uses even more conservative 5–7 s delays given its size.

---

## 5. Caveats

- **JS-rendered vendors** (`mylife`, `city-plumbing`) need Playwright: `pip install playwright && playwright install chromium`. Install it in the `apps/api` venv. SSR vendors never pull the browser in.
- **Genesis prices are often `null`** because most products are option-based (variable) WooCommerce products — only prices present on the page are extracted.
- **Crosswater** resolves every product to the `crosswater/all` fallback category (there's no normalized `all` mapping), since discovery is driven by the sitemap rather than category pages.
- **Warren Keys** is **manual curation only** — it refuses to run without `--curated <rows.json|rows.csv>` (20–30 tile ranges curated from its PDF brochures) and is not a live crawl.
- Products without a dimension parse (`dimensions_confidence=None`) still get a model, but the unscaled axes stay at the generic builder size.
