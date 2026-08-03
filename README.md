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

## Import a plan from a photo (fully offline)

In the Room panel, **"Import plan from photo"** uploads a photo of a hand-drawn plan / measurement
sketch. The backend sends it to your **own local** OCR/vision model, gets back the room geometry
(floor outline in mm, wall shapes, doors, windows), and drops it into the editor — no external API.

**Licensing (checked): everything is MIT.** `llama.cpp` is MIT-licensed (`Copyright (c) 2023-2026
The ggml authors`), and the recommended `baidu/Unlimited-OCR` model is MIT (as is its
DeepSeek-OCR base). You may freely run, modify, and bundle all of it for your own app; just keep
the MIT copyright notices.

Serving your own model (recommended — Unlimited-OCR, a 3B OCR specialist that reads handwriting
well, Q4 ~1.8GB + 774MB mmproj):

```bash
scripts/serve-ocr.sh            # downloads GGUF+mmproj to ~/.local/share/bathroom-ocr, starts
                                # llama-server with --mmproj on 127.0.0.1:9333
```

The app defaults `PLAN_VISION_BASE_URL` to that local endpoint (`http://127.0.0.1:9333/v1`), so
it works with no extra config once the server is up. `GET /api/v1/plans/status` reports whether
it's configured.

> ⚠️ **Unlimited-OCR needs a DeepSeek-OCR-aware llama.cpp build (PR #17400)** — the model uses
> the DeepSeek-OCR architecture (SAM+CLIP DeepEncoder + DeepSeek-V2 MoE), which isn't in upstream
> `main` yet. Build that branch:
> `git fetch origin pull/24975/head:pr24975 && git checkout pr24975` then build `llama-server`
> (`-DGGML_CUDA=ON` for NVIDIA). Your homelab `.5` llama.cpp already has the CUDA build flow.
>
> If you'd rather use a **stock llama.cpp** build, swap `PLAN_VISION_MODEL` to a
> Gemma 4 E2B/12B GGUF (`unsloth/gemma-4-E2B-it-GGUF` + its mmproj) — same OpenAI-compatible
> interface, one-line change, though tiny Gemma reads handwriting less reliably than
> Unlimited-OCR.

```bash
# custom endpoints if not using the default
export PLAN_VISION_BASE_URL=http://<host>:9333/v1
export PLAN_VISION_MODEL=Unlimited-OCR-Q4_K_M   # or leave unset (server default)
export PLAN_VISION_API_KEY=                       # only if your server needs one
```

If the local server isn't running, the endpoint returns a clear 502/503 and the room stays
drawable by hand.

## Testing

Verified end-to-end in a real browser (Brave): draw room → add doors/windows → place 6 products → tile floor + walls → save → export BOM + CSV. Three bugs found and fixed during test loops: a camera/grid NaN crash when entering draw mode, a keyboard-handler crash on non-element event targets, and a save-blocking schema field-name mismatch (camelCase frontend vs snake_case backend).
