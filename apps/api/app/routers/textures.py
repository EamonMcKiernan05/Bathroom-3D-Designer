"""Texture endpoints (doc 04 §2.2)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Texture, TextureMap
from ..schemas import TextureSummary

router = APIRouter(prefix="/api/v1", tags=["textures"])


def _to_summary(t: Texture) -> TextureSummary:
    s = TextureSummary.model_validate(t)
    for m in t.maps:
        if m.map_type == "albedo":
            s.albedo_url = m.file_url
        elif m.map_type == "normal":
            s.normal_url = m.file_url
        elif m.map_type == "roughness":
            s.roughness_url = m.file_url
        elif m.map_type == "preview":
            s.preview_url = m.file_url
    return s


@router.get("/textures", response_model=list[TextureSummary])
def list_textures(
    category: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Texture).where(Texture.active == True)  # noqa: E712
    if category:
        query = query.where(Texture.category == category)
    textures = db.scalars(query.order_by(Texture.name)).all()
    return [_to_summary(t) for t in textures]


@router.get("/textures/{texture_id}", response_model=TextureSummary)
def get_texture(texture_id: int, db: Session = Depends(get_db)):
    from fastapi import HTTPException

    t = db.get(Texture, texture_id)
    if not t:
        raise HTTPException(404, "Texture not found")
    return _to_summary(t)
