"""Pydantic schemas."""
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- Products ----------
class ProductSummary(BaseModel):
    id: int
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    price_gbp: Optional[float] = None
    price_note: Optional[str] = None
    price_is_from: bool = False
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    finishes: list = []
    colours: list = []
    variant_data: dict = {}
    model_url: Optional[str] = None
    model_status: str = "pending"
    main_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    retailer_name: Optional[str] = None
    retailer_slug: Optional[str] = None
    retailer_website: Optional[str] = None
    retailer_sku: Optional[str] = None
    model_scale: float = 1.0
    placeholder_kind: str = "generic_shape"

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    items: list[ProductSummary]
    total: int
    page: int
    per_page: int
    pages: int


class CategorySummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    slug: str
    name: str
    depth: int = 0
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    product_count: int = 0


class RetailerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    slug: str
    name: str
    website_url: str
    country: str


# ---------- Textures ----------
class TextureSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    slug: str
    name: str
    category: str
    tile_width_mm: float
    tile_height_mm: float
    thickness_mm: Optional[float] = None
    colour_family: Optional[str] = None
    finish: Optional[str] = None
    material: Optional[str] = None
    pattern: Optional[str] = None
    source_type: str = "scraped"
    albedo_url: Optional[str] = None
    normal_url: Optional[str] = None
    roughness_url: Optional[str] = None
    preview_url: Optional[str] = None


# ---------- Designs ----------
# These mirror the frontend's PlacedItem / TextureAssignment / DesignData shapes
# (design.data is stored raw as JSONB and round-tripped as-is to the client).
class PlacedItemSchema(BaseModel):
    id: str
    productId: Optional[int] = None
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    position: list[float]
    rotation: float = 0
    scale: float = 1000
    modelUrl: Optional[str] = None
    wallMounted: bool = False
    mountHeight: float = 0
    widthMm: Optional[float] = None
    heightMm: Optional[float] = None
    depthMm: Optional[float] = None
    finish: Optional[str] = None
    metadata: dict = {}


class TextureAssignmentSchema(BaseModel):
    textureId: Optional[int] = None
    tileWidthMm: float = 0
    tileHeightMm: float = 0
    groutWidthMm: float = 3
    groutColor: str = "#cccccc"
    layout: str = "straight"
    rotation: float = 0
    url: Optional[str] = None
    name: Optional[str] = None
    solidColor: Optional[str] = None


class DesignDataSchema(BaseModel):
    room: dict = {}
    doors: list[dict] = []
    windows: list[dict] = []
    items: list[PlacedItemSchema] = []
    floorTexture: Optional[TextureAssignmentSchema] = None
    wallTextures: dict = {}
    ceilingTexture: Optional[TextureAssignmentSchema] = None
    version: int = 1


class DesignCreate(BaseModel):
    name: str = "Untitled Design"
    description: Optional[str] = None
    data: DesignDataSchema


class DesignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data: Optional[DesignDataSchema] = None
    thumbnail_url: Optional[str] = None


class DesignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    data: dict
    thumbnail_url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------- BOM ----------
class BomItem(BaseModel):
    product_name: str
    retailer_name: str
    retailer_url: Optional[str] = None
    sku: str
    finish: Optional[str] = None
    quantity: int
    unit_price: Optional[float] = None
    total_price: Optional[float] = None


class BomResponse(BaseModel):
    design_id: int
    design_name: str
    items: list[BomItem]
    grand_total: Optional[float] = None
    generated_at: str
