"""Image pipeline (doc 02 §3.2): download → resize ≤1200px → WebP q85 → 256px thumb.

Local dev: writes to assets/products/<retailer_slug>/<sku>/ and returns
URL paths (/products/...). Production (MINIO_ENDPOINT set): uploads to S3
and returns object keys.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from .. import config

log = logging.getLogger("scraper.images")

_s3 = None
_s3_bucket = None


def _get_s3():
    global _s3, _s3_bucket
    if _s3 is None:
        import boto3
        from botocore.client import Config as BotoConfig

        _s3 = boto3.client(
            "s3",
            endpoint_url=config.MINIO_ENDPOINT,
            aws_access_key_id=config.MINIO_ACCESS_KEY,
            aws_secret_access_key=config.MINIO_SECRET_KEY,
            region_name="us-east-1",
            config=BotoConfig(s3={"addressing_style": "path"}),
        )
        _s3_bucket = config.MINIO_BUCKET
    return _s3, _s3_bucket


def _process(data: bytes) -> tuple[bytes, bytes]:
    """Return (webp ≤1200px, thumb 256px) byte strings."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")

    def _resize(img: Image.Image, max_w: int) -> Image.Image:
        if img.width > max_w:
            h = int(img.height * max_w / img.width)
            img = img.resize((max_w, h), Image.LANCZOS)
        return img

    full = _resize(img, config.MAX_IMAGE_WIDTH)
    thumb = _resize(img, config.THUMB_SIZE)

    buf1, buf2 = io.BytesIO(), io.BytesIO()
    full.save(buf1, "WEBP", quality=config.IMAGE_QUALITY, method=4)
    thumb.save(buf2, "WEBP", quality=config.IMAGE_QUALITY, method=4)
    return buf1.getvalue(), buf2.getvalue()


def store_image(
    http_get,  # callable(url) -> bytes | None (PoliteSession.fetch_bytes)
    url: str,
    retailer_slug: str,
    sku: str,
    index: int,
) -> tuple[str | None, str | None]:
    """Download + store one image. Returns (main_url, thumb_url) or (None, None).

    `http_get` is bound to the vendor's session so image hosts get the same
    UA/cookies and delays apply.
    """
    data = http_get(url)
    if not data:
        log.warning("  image download failed: %s", url)
        return None, None

    try:
        webp, thumb = _process(data)
    except Exception as e:
        log.warning("  image processing failed %s: %s", url, e)
        return None, None

    filename = f"img_{index:02d}.webp"
    thumbname = f"img_{index:02d}_thumb.webp"
    key_dir = f"{retailer_slug}/{sku}"

    if config.MINIO_ENDPOINT:
        s3, bucket = _get_s3()
        try:
            s3.put_object(Bucket=bucket, Key=f"products/{key_dir}/{filename}", Body=webp, ContentType="image/webp")
            s3.put_object(Bucket=bucket, Key=f"products/{key_dir}/{thumbname}", Body=thumb, ContentType="image/webp")
            return f"products/{key_dir}/{filename}", f"products/{key_dir}/{thumbname}"
        except Exception as e:
            log.warning("  minio upload failed: %s", e)
            return None, None

    # local dev
    out_dir = config.PRODUCT_IMAGE_DIR / key_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / filename).write_bytes(webp)
    (out_dir / thumbname).write_bytes(thumb)
    return f"/products/{key_dir}/{filename}", f"/products/{key_dir}/{thumbname}"
