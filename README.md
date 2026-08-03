# Bathroom 3D Designer

Browser-based 3D bathroom design tool. Draw your room, place real products, tile the walls and floor, and export a shopping list — all in real-time 3D, running in your browser.

Built from the planning docs in `O:\projects\Bathroom Design`. Fully working local demo — **web scraping is deliberately not part of this build** (deferred until the app is functional per the plan).

## Quick start

Prerequisites: Node 20+ and Python 3.11+. The repo ships its own portable **PostgreSQL 16** (no system install needed).

```powershell
# 1. Start the database (first time also seeds it)
scripts\start-db.bat

# 2. Start the API (in a new terminal)
cd apps\api
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload

# 3. Start the web app (in a new terminal)
cd apps\web
npm run dev
```

Open **http://localhost:5174** in your browser. (If the API proxy ever 500s, make sure step 2 is running on port 8000.)

One-time setup (fresh clone):

```powershell
# DB
scripts\start-db.bat          # extracts + initdb + starts postgres on 5432, creates db user + bathroom_designer

# API venv
cd apps\api
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.seed     # seeds retailers, categories, 24 demo products, 21 textures

# Web deps
cd apps\web
npm install
```

## What's implemented (working demo)

- **Room builder** — draw a rectangular/L-shaped room by clicking points on the floor grid, or edit a default 2400×1800 room. Doors & windows placed via a wall-picker form (or click a wall). Fully lit, no shadows — basic 3D visualisation by design.
- **Product placement** — 24 demo products (toilet, basin, bath, shower tray/screen, radiator, towel rail, mirror, vanity, taps, shower set, accessories) with **17 parametric Blender-generated GLB models** (real-world mm scale, Draco-compressed). Drag from the catalogue or "+ Add to room"; move by dragging or editing position in the properties panel; rotate (R key), delete (Del), undo/redo (Ctrl+Z / Ctrl+Shift+Z) with a 50-step history. Snap-to-wall and AABB collision-highlighting included.
- **Surfaces & tiles** — 21 procedural tile/panel/floor textures (subway, marble, metro, mosaic, porcelain, terrazzo, encaustic, wood plank, panels, ceiling) with real-world dimensions, straight or diagonal layouts, grout width/colour presets. Apply to any wall, the floor, the ceiling, or "All walls". UVs are world-space so tiles repeat at exact real-world scale.
- **Save / load** — Save pushes the full design (room + openings + items + textures) to PostgreSQL (JSONB). Saved designs listed on `/designs`, reopen in the editor, or view read-only in 3D. Auto-name + inline rename in the toolbar.
- **Export** — Bill of Materials (grouped by retailer) in the export dialog, downloadable CSV, and copy-to-clipboard shopping list. 2D floorplan PNG export.

## Tech stack

| Layer | Tech |
|-------|------|
| Frontend | React 19 + TypeScript + Vite 6 + Three.js (React Three Fiber) + drei + Zustand + Tailwind 4 |
| Backend | FastAPI + SQLAlchemy 2 (portable: PostgreSQL JSONB, SQLite fallback) |
| Database | PostgreSQL 16 (portable binaries in `scripts/pgsql`, data in `scripts/pgdata`) |
| 3D models | Blender 5.2 via blender-mcp (parametric, exported GLB) — `packages/model-gen` |
| Textures | Procedurally generated with Pillow — `packages/texture-proc` |
| Units | **Millimetres** everywhere (1 Three.js unit = 1 mm). GLBs from Blender are metre-scale, scaled ×1000 on load |

## Repo layout

```
apps/
  web/          React 3D editor + catalogue + surfaces + save/load + BOM
  api/          FastAPI: /api/v1/products, /textures, /designs, BOM; serves assets
packages/
  model-gen/    Blender parametric model generators (headless batch + thumbnails)
  texture-proc/ Procedural tile/panel texture generator (Pillow) -> manifest.json
assets/
  models/       Generated GLB files (17)
  textures/     Generated texture sets (21) + manifest.json
  thumbnails/   Blender EEVEE render thumbs for the catalogue
scripts/
  start-db.bat  One-shot portable-PostgreSQL setup/start
```

## Design decisions honoured (from the plan)

- **mm units** internally (user decision) — 1 unit = 1 mm; GLBs scaled ×1000 on import.
- **No scraping** in this build — 24 curated demo products; per-vendor scrapers are the next phase.
- **No AI / bought models** — all 17 models are parametric primitives built in Blender.
- **Fully lit, no shadows**, straight + diagonal tile layouts (herringbone/brick deferred), plain PostgreSQL (no PostGIS).
- **Auth deferred** — API is open for local testing; add auth before any public launch.

## Import a plan from a photo

In the Room panel, **"Import plan from photo"** lets you upload a clear photo of a hand-drawn
bathroom plan / measurement sketch. The backend sends it to a local Vision LLM, gets back the
room geometry (floor outline in mm, wall shapes, doors, windows), and drops it straight into the
editor where you can then tweak walls in the 2D editor.

The vision model is any **OpenAI-compatible multimodal endpoint** — the natural fit is a Gemma 4
edge model on your existing homelab llama.cpp.

```bash
# serve Gemma 4 E2B (tiny, ~5GB) or 12B (better at reading handwriting) with vision
llama-server -m <text>.gguf --mmproj <mmproj>.gguf -c 8192 --port 8080

# point the app at it
export PLAN_VISION_BASE_URL=http://127.0.0.1:8080/v1
export PLAN_VISION_MODEL=gemma-4-E2B-it        # or gemma-4-12b-it
export PLAN_VISION_API_KEY=                    # optional
```

Without these env vars the endpoint returns a clear 503 (no model configured) — the room stays
drawable by hand. Model accuracy note: reading messy handwriting is the weak point of the tiny
E2B/E4B edge models; the 12B Gemma 4 reads hand-drawn measurements far more reliably. Same
interface either way, so it's a one-line env swap.

## Testing

Verified end-to-end in a real browser (Brave): draw room → add doors/windows → place 6 products → tile floor + walls → save → export BOM + CSV. Three bugs found and fixed during test loops: a camera/grid NaN crash when entering draw mode, a keyboard-handler crash on non-element event targets, and a save-blocking schema field-name mismatch (camelCase frontend vs snake_case backend).
