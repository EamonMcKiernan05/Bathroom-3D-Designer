"""Scraper CLI (doc 02 §4, Phase 6.5).

    python -m scraper.cli --retailer ideal-bathrooms            # live run
    python -m scraper.cli --retailer ideal-bathrooms --dry-run    # no DB writes
    python -m scraper.cli --all --limit 20
    python -m scraper.cli --retailer warren-keys --curated curated.json
    python -m scraper.cli --retailer ideal-bathrooms --categories toilets,vanity-units

Run with the apps/api venv python (needs requests, Pillow, SQLAlchemy, psycopg2).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow `python -m scraper.cli` from the packages/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from . import config  # noqa: E402
from .shared import db as dbapi  # noqa: E402
from .vendors import PRIORITY_ORDER, REGISTRY  # noqa: E402


def _build_parser():
    p = argparse.ArgumentParser(description="Bathroom Designer scraper (doc 02 / Phase 6)")
    p.add_argument("--retailer", help="Retailer slug (see --list)")
    p.add_argument("--all", action="store_true", help="Run all retailers in priority order")
    p.add_argument("--list", action="store_true", help="List available retailers")
    p.add_argument("--dry-run", action="store_true", help="Fetch + extract, but write nothing to DB")
    p.add_argument("--limit", type=int, default=None, help="Max products per vendor")
    p.add_argument("--categories", default=None, help="Comma-separated vendor category keys to run")
    p.add_argument("--curated", default=None, help="warren-keys: path to curated rows file (JSON/CSV)")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p


def _run_vendor(slug: str, args) -> dict:
    cls = REGISTRY[slug]
    categories = args.categories.split(",") if args.categories else None
    scraper = cls(
        dry_run=args.dry_run,
        limit=args.limit,
        categories=categories,
        curated=args.curated,
    )
    print(f"\n=== {slug} ({'DRY-RUN' if args.dry_run else 'live'}"
          f"{', limit ' + str(args.limit) if args.limit else ''}) ===")
    stats = scraper.run()
    print(f"    {slug} done: {stats}")
    return stats


def main():
    args = _build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if args.list:
        print("Available retailers (priority order):")
        for s in PRIORITY_ORDER:
            print(f"  {s:20} {REGISTRY[s].__doc__ and REGISTRY[s].__doc__.strip().splitlines()[0]}")
        return

    if not args.dry_run:
        dbapi.ensure_schema()

    slugs = [args.retailer] if args.retailer else (PRIORITY_ORDER if args.all else None)
    if not slugs:
        print("Specify --retailer <slug> or --all (see --list).", file=sys.stderr)
        sys.exit(1)

    totals = {}
    for slug in slugs:
        if slug not in REGISTRY:
            print(f"Unknown retailer '{slug}'. See --list.", file=sys.stderr)
            sys.exit(1)
        try:
            totals[slug] = _run_vendor(slug, args)
        except Exception as e:
            print(f"\n[ERROR] {slug}: {e}", file=sys.stderr)
            totals[slug] = {"error": str(e)}

    print("\n=== Summary ===")
    for slug, stats in totals.items():
        print(f"  {slug}: {stats}")


if __name__ == "__main__":
    main()