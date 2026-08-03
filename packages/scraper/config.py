"""Shared scraper configuration (doc 02 §1 Shared Configuration)."""
import os
from pathlib import Path

# Repo root: packages/scraper -> packages -> root
ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = ROOT / "assets"
PRODUCT_IMAGE_DIR = ASSETS / "products"  # <retailer_slug>/<sku>/img_N.webp (+ _thumb_N.webp)
API_DIR = ROOT / "apps" / "api"

# Polite crawling (doc 00 §9): 2-5s between requests.
MIN_DELAY_S = float(os.environ.get("SCRAPER_MIN_DELAY", "2.0"))
MAX_DELAY_S = float(os.environ.get("SCRAPER_MAX_DELAY", "5.0"))
MAX_RETRIES = int(os.environ.get("SCRAPER_MAX_RETRIES", "3"))
RETRY_BACKOFF_S = 5.0
REQUEST_TIMEOUT_S = 30

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Image pipeline (doc 02 §3.2): resize to max width, WebP q85, 256px thumb.
MAX_IMAGE_WIDTH = 1200
IMAGE_QUALITY = 85
THUMB_SIZE = 256

# MinIO (production). When MINIO_ENDPOINT is set, images upload to S3 instead
# of the local assets dir. Local dev = assets dir, served by FastAPI.
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "bathroom-assets")

# Database URL — reuse the API's default (local portable PostgreSQL).
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://bathroom:bathroom@127.0.0.1:5432/bathroom_designer",
)

# Transparency header (doc 02 §5)
PURPOSE_HEADER = "X-Purpose: Product catalogue aggregation"

# Per-vendor page limit (None = unlimited). Mostly useful for dev runs.
DEFAULT_LIMIT = int(os.environ.get("SCRAPER_LIMIT", "0")) or None
