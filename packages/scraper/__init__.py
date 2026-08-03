"""Bathroom 3D Designer — web scraping pipeline (doc 02 / Phase 6).

Per-vendor scrapers writing into the shared product schema. Run with the
apps/api venv python (needs requests, Pillow, SQLAlchemy, psycopg2):

    python -m scraper.cli --retailer ideal-bathrooms          # live run
    python -m scraper.cli --retailer ideal-bathrooms --dry-run  # no DB writes
    python -m scraper.cli --all --limit 20

Priority order (doc 02 §2 / Phase 6.2): Ideal Bathrooms IoM → Genesis →
MyLife → Crosswater → Warren Keys (manual curation) → City Plumbing (last).
"""
