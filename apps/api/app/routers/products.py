"""Product & catalogue endpoints (doc 04 §2.2)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Category, Product, Retailer
from ..schemas import (
    CategorySummary,
    ProductListResponse,
    ProductSummary,
    RetailerSummary,
)

router = APIRouter(prefix="/api/v1", tags=["catalogue"])


def _to_summary(p: Product, retailer: Retailer | None = None) -> ProductSummary:
    s = ProductSummary.model_validate(p)
    if retailer:
        s.retailer_name = retailer.name
        s.retailer_slug = retailer.slug
        s.retailer_website = retailer.website_url
    return s


@router.get("/products", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    category: str | None = None,
    retailer: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    finish: str | None = None,
    q: str | None = None,
    sort: str = Query("name", enum=["name", "price_asc", "price_desc", "newest"]),
    db: Session = Depends(get_db),
):
    query = select(Product).where(Product.active == True)  # noqa: E712
    if category:
        query = query.where(Product.category.like(f"{category}%"))
    if retailer:
        query = query.join(Retailer).where(Retailer.slug == retailer)
    if min_price is not None:
        query = query.where(Product.price_gbp >= min_price)
    if max_price is not None:
        query = query.where(Product.price_gbp <= max_price)
    if finish:
        query = query.where(Product.finishes.contains([finish]))
    if q:
        like = f"%{q}%"
        query = query.where(
            or_(Product.name.ilike(like), Product.brand.ilike(like), Product.retailer_sku.ilike(like))
        )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    if sort == "price_asc":
        query = query.order_by(Product.price_gbp.asc().nullslast())
    elif sort == "price_desc":
        query = query.order_by(Product.price_gbp.desc().nullsfirst())
    elif sort == "newest":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.name)

    query = query.offset((page - 1) * per_page).limit(per_page)
    products = db.scalars(query).all()
    retailer_map = {r.id: r for r in db.scalars(select(Retailer)).all()}

    return ProductListResponse(
        items=[_to_summary(p, retailer_map.get(p.retailer_id)) for p in products],
        total=total,
        page=page,
        per_page=per_page,
        pages=max(1, (total + per_page - 1) // per_page),
    )


@router.get("/products/{product_id}", response_model=ProductSummary)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if not p:
        from fastapi import HTTPException

        raise HTTPException(404, "Product not found")
    r = db.get(Retailer, p.retailer_id)
    return _to_summary(p, r)


@router.get("/categories", response_model=list[CategorySummary])
def list_categories(db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).order_by(Category.sort_order, Category.name)).all()
    counts = dict(
        db.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.active == True)  # noqa: E712
            .group_by(Product.category)
        ).all()
    )
    out = []
    for c in cats:
        s = CategorySummary.model_validate(c)
        s.product_count = counts.get(c.slug, 0)
        out.append(s)
    return out


@router.get("/retailers", response_model=list[RetailerSummary])
def list_retailers(db: Session = Depends(get_db)):
    return db.scalars(select(Retailer).order_by(Retailer.name)).all()


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(20, le=50), db: Session = Depends(get_db)):
    like = f"%{q}%"
    products = db.scalars(
        select(Product)
        .where(Product.active == True, or_(Product.name.ilike(like), Product.brand.ilike(like)))  # noqa: E712
        .limit(limit)
    ).all()
    retailer_map = {r.id: r for r in db.scalars(select(Retailer)).all()}
    return [s.model_dump() for s in (_to_summary(p, retailer_map.get(p.retailer_id)) for p in products)]
