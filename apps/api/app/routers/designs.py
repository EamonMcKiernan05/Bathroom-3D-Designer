"""Design CRUD + BOM export (doc 04 §2.2, Phase 4)."""
import csv
import io
import json
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Design, DesignItem, Product, Retailer
from ..schemas import BomItem, BomResponse, DesignCreate, DesignResponse, DesignUpdate

router = APIRouter(prefix="/api/v1/designs", tags=["designs"])


def _to_response(d: Design) -> DesignResponse:
    return DesignResponse(
        id=d.id,
        name=d.name,
        description=d.description,
        data=d.data or {},
        thumbnail_url=d.thumbnail_url,
        created_at=d.created_at.isoformat() if d.created_at else None,
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
    )


@router.get("", response_model=list[DesignResponse])
def list_designs(db: Session = Depends(get_db)):
    designs = db.scalars(
        select(Design).where(Design.is_archived == False).order_by(Design.updated_at.desc())  # noqa: E712
    ).all()
    return [_to_response(d) for d in designs]


@router.post("", response_model=DesignResponse, status_code=201)
def create_design(payload: DesignCreate, db: Session = Depends(get_db)):
    design = Design(
        name=payload.name,
        description=payload.description,
        data=payload.data.model_dump() if payload.data else {},
    )
    db.add(design)
    db.flush()
    _sync_design_items(db, design)
    db.commit()
    db.refresh(design)
    return _to_response(design)


@router.get("/{design_id}", response_model=DesignResponse)
def get_design(design_id: int, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    return _to_response(d)


@router.put("/{design_id}", response_model=DesignResponse)
def update_design(design_id: int, payload: DesignUpdate, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    if payload.name is not None:
        d.name = payload.name
    if payload.description is not None:
        d.description = payload.description
    if payload.data is not None:
        d.data = payload.data.model_dump()
    if payload.thumbnail_url is not None:
        d.thumbnail_url = payload.thumbnail_url
    d.updated_at = datetime.utcnow()
    db.flush()
    _sync_design_items(db, d)
    db.commit()
    db.refresh(d)
    return _to_response(d)


@router.delete("/{design_id}", status_code=204)
def delete_design(design_id: int, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    db.delete(d)
    db.commit()
    return Response(status_code=204)


@router.post("/{design_id}/share", response_model=dict)
def share_design(design_id: int, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    if not d.share_token:
        d.share_token = secrets.token_hex(16)
        d.is_public = True
        db.commit()
    return {"share_token": d.share_token, "url": f"/share/{d.share_token}"}


def _sync_design_items(db: Session, design: Design) -> None:
    """Mirror placed items into design_items for queryability (doc 05)."""
    db.query(DesignItem).filter(DesignItem.design_id == design.id).delete()
    data = design.data or {}
    for item in data.get("items", []):
        pos = item.get("position", [0, 0, 0])
        db.add(
            DesignItem(
                design_id=design.id,
                product_id=item.get("productId"),
                position_x=pos[0],
                position_y=pos[1] if len(pos) > 1 else 0,
                position_z=pos[2] if len(pos) > 2 else 0,
                rotation_y=item.get("rotation", 0),
                finish=item.get("finish"),
            )
        )


def _bom_for(db: Session, design: Design) -> BomResponse:
    data = design.data or {}
    items = data.get("items", [])
    rows = []
    for item in items:
        pid = item.get("productId")
        prod = db.get(Product, pid) if pid else None
        if not prod:
            continue
        retailer = db.get(Retailer, prod.retailer_id)
        qty = 1
        unit = float(prod.price_gbp) if prod.price_gbp is not None else None
        rows.append(
            BomItem(
                product_name=prod.name,
                retailer_name=retailer.name if retailer else "",
                retailer_url=prod.retailer_url,
                sku=prod.retailer_sku,
                finish=item.get("finish"),
                quantity=qty,
                unit_price=unit,
                total_price=unit if unit is not None else None,
            )
        )
    priced = [r for r in rows if r.total_price is not None]
    grand = round(sum(r.total_price for r in priced), 2) if priced else None
    return BomResponse(
        design_id=design.id,
        design_name=design.name,
        items=rows,
        grand_total=grand,
        generated_at=datetime.utcnow().isoformat(),
    )


@router.get("/{design_id}/bom", response_model=BomResponse)
def get_bom(design_id: int, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    return _bom_for(db, d)


@router.get("/{design_id}/bom.csv")
def get_bom_csv(design_id: int, db: Session = Depends(get_db)):
    d = db.get(Design, design_id)
    if not d:
        raise HTTPException(404, "Design not found")
    bom = _bom_for(db, d)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Product", "Retailer", "SKU", "Finish", "Qty", "Unit Price (GBP)", "Total (GBP)", "URL"])
    for r in bom.items:
        writer.writerow(
            [
                r.product_name,
                r.retailer_name,
                r.sku,
                r.finish or "",
                r.quantity,
                r.unit_price,
                r.total_price,
                r.retailer_url or "",
            ]
        )
    writer.writerow([])
    writer.writerow(["GRAND TOTAL", "", "", "", "", "", bom.grand_total or 0, ""])
    filename = f"bom-{design_id}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/shared/{token}", response_model=DesignResponse)
def get_shared(token: str, db: Session = Depends(get_db)):
    d = db.scalar(select(Design).where(Design.share_token == token, Design.is_public == True))  # noqa: E712
    if not d:
        raise HTTPException(404, "Shared design not found")
    return _to_response(d)
