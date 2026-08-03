"""Admin/ops endpoints (doc 02 §4, Phase 6.6 + model batch status).

  GET /api/v1/admin/scrape-status  — last run per retailer with counts
  GET /api/v1/admin/model-status    — model generation queue status
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ModelJob, Product, Retailer, ScrapeJob

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/scrape-status")
def scrape_status(db: Session = Depends(get_db)):
    """Most recent scrape job per retailer + running/aged jobs."""
    retailers = db.scalars(select(Retailer).order_by(Retailer.name)).all()
    rows = []
    for r in retailers:
        last = db.scalar(
            select(ScrapeJob)
            .where(ScrapeJob.retailer_id == r.id)
            .order_by(ScrapeJob.started_at.desc())
            .limit(1)
        )
        latest = None
        if last:
            latest = {
                "job_type": last.job_type,
                "status": last.status,
                "products_found": last.products_found,
                "products_new": last.products_new,
                "products_updated": last.products_updated,
                "products_failed": last.products_failed,
                "started_at": last.started_at.isoformat() if last.started_at else None,
                "completed_at": last.completed_at.isoformat() if last.completed_at else None,
                "duration_secs": last.duration_secs,
                "errors": last.errors or [],
            }
        rows.append(
            {
                "slug": r.slug,
                "name": r.name,
                "scrape_enabled": r.scrape_enabled,
                "last_run": latest,
            }
        )
    # running/aged jobs across all retailers
    running = db.execute(
        select(ScrapeJob).where(ScrapeJob.status == "running")
    ).scalars().all()
    return {"retailers": rows, "running_jobs": [j.id for j in running], "count": len(rows)}


@router.get("/model-status")
def model_status(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Product.model_status, func.count(Product.id))
            .where(Product.category.isnot(None))
            .group_by(Product.model_status)
        ).all()
    )
    pending = db.scalars(
        select(Product)
        .where(Product.model_status == "pending")
        .order_by(Product.updated_at.desc())
        .limit(50)
    ).all()
    recent_jobs = db.scalars(
        select(ModelJob).order_by(ModelJob.queued_at.desc()).limit(25)
    ).all()
    return {
        "status_counts": {k: v for k, v in counts.items()},
        "pending_count": len(pending),
        "pending_products": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "width_mm": float(p.width_mm) if p.width_mm else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in pending
        ],
        "recent_jobs": [
            {
                "id": j.id,
                "product_id": j.product_id,
                "method": j.method,
                "status": j.status,
                "output_url": j.output_url,
                "polygon_count": j.polygon_count,
                "file_size_kb": j.file_size_kb,
                "error_message": j.error_message,
            }
            for j in recent_jobs
        ],
    }
