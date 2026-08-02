"""SQLAlchemy models — mirror of doc 05 DDL. JSONB on PostgreSQL, JSON on SQLite."""
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .db import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class Retailer(Base):
    __tablename__ = "retailers"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    website_url = Column(String(500), nullable=False)
    logo_url = Column(String(500))
    country = Column(String(10), default="UK")
    scrape_enabled = Column(Boolean, default=True)
    scrape_config = Column(JSONType, default=dict)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    products = relationship("Product", back_populates="retailer")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"))
    depth = Column(SmallInteger, default=0)
    icon = Column(String(50))
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    retailer_id = Column(Integer, ForeignKey("retailers.id"), nullable=False)
    retailer_sku = Column(String(100), nullable=False)
    retailer_url = Column(String(1000))
    name = Column(String(500), nullable=False)
    brand = Column(String(200))
    category_id = Column(Integer, ForeignKey("categories.id"))
    category = Column(String(200))  # denormalized slug for fast filtering
    description = Column(Text)
    price_gbp = Column(Numeric(10, 2))
    price_note = Column(String(50))
    price_is_from = Column(Boolean, default=False)
    width_mm = Column(Numeric(8, 1))
    height_mm = Column(Numeric(8, 1))
    depth_mm = Column(Numeric(8, 1))
    diameter_mm = Column(Numeric(8, 1))
    weight_kg = Column(Numeric(6, 2))
    dimensions_confidence = Column(String(10))
    placeholder_kind = Column(String(20), default="generic_shape")
    finishes = Column(JSONType, default=list)
    colours = Column(JSONType, default=list)
    sizes = Column(JSONType, default=list)
    variant_data = Column(JSONType, default=dict)
    model_url = Column(String(500))
    model_status = Column(String(20), default="pending")
    model_method = Column(String(20))
    model_polygons = Column(Integer)
    model_file_kb = Column(Integer)
    needs_model_update = Column(Boolean, default=False)
    main_image_url = Column(String(500))
    thumbnail_url = Column(String(500))
    active = Column(Boolean, default=True)
    in_stock = Column(Boolean)
    first_scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    last_scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    retailer = relationship("Retailer", back_populates="products")
    images = relationship("ProductImage", back_populates="product")

    __table_args__ = ({"sqlite_autoincrement": True},)


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(500), nullable=False)
    original_url = Column(String(1000))
    alt_text = Column(String(500))
    sort_order = Column(Integer, default=0)
    is_primary = Column(Boolean, default=False)
    width_px = Column(Integer)
    height_px = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="images")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku = Column(String(100))
    name = Column(String(500))
    finish = Column(String(100))
    colour = Column(String(100))
    size = Column(String(100))
    price_gbp = Column(Numeric(10, 2))
    width_mm = Column(Numeric(8, 1))
    height_mm = Column(Numeric(8, 1))
    depth_mm = Column(Numeric(8, 1))
    model_url = Column(String(500))
    in_stock = Column(Boolean)
    retailer_url = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Texture(Base):
    __tablename__ = "textures"

    id = Column(Integer, primary_key=True)
    slug = Column(String(200), unique=True, nullable=False)
    name = Column(String(300), nullable=False)
    category = Column(String(50), nullable=False)
    tile_width_mm = Column(Numeric(8, 1), nullable=False)
    tile_height_mm = Column(Numeric(8, 1), nullable=False)
    thickness_mm = Column(Numeric(8, 1))
    colour_family = Column(String(50))
    finish = Column(String(50))
    material = Column(String(100))
    pattern = Column(String(50))
    source_type = Column(String(20), default="scraped")
    source_url = Column(String(1000))
    retailer_id = Column(Integer, ForeignKey("retailers.id"))
    license = Column(String(50), default="scraped")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    maps = relationship("TextureMap", back_populates="texture")


class TextureMap(Base):
    __tablename__ = "texture_maps"

    id = Column(Integer, primary_key=True)
    texture_id = Column(Integer, ForeignKey("textures.id", ondelete="CASCADE"), nullable=False)
    map_type = Column(String(20), nullable=False)  # albedo, normal, roughness, height, ao
    file_url = Column(String(500), nullable=False)
    file_size_kb = Column(Integer)
    width_px = Column(Integer)
    height_px = Column(Integer)
    format = Column(String(10), default="webp")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    texture = relationship("Texture", back_populates="maps")


class Design(Base):
    __tablename__ = "designs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)  # auth deferred — nullable for anonymous
    name = Column(String(300), nullable=False, default="Untitled Design")
    description = Column(Text)
    thumbnail_url = Column(String(500))
    data = Column(JSONType, nullable=False, default=dict)
    share_token = Column(String(32), unique=True)
    is_public = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("DesignItem", back_populates="design", cascade="all, delete-orphan")


class DesignItem(Base):
    __tablename__ = "design_items"

    id = Column(Integer, primary_key=True)
    design_id = Column(Integer, ForeignKey("designs.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"))
    position_x = Column(Numeric(8, 4), nullable=False)
    position_y = Column(Numeric(8, 4), nullable=False, default=0)
    position_z = Column(Numeric(8, 4), nullable=False)
    rotation_y = Column(Numeric(6, 4), default=0)
    finish = Column(String(100))
    size_variant = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    design = relationship("Design", back_populates="items")


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id = Column(Integer, primary_key=True)
    retailer_id = Column(Integer, ForeignKey("retailers.id"), nullable=False)
    job_type = Column(String(20), nullable=False)
    status = Column(String(20), default="running")
    products_found = Column(Integer, default=0)
    products_new = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    products_failed = Column(Integer, default=0)
    errors = Column(JSONType, default=list)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    duration_secs = Column(Integer)


class ModelJob(Base):
    __tablename__ = "model_jobs"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    method = Column(String(20), nullable=False)
    status = Column(String(20), default="queued")
    output_url = Column(String(500))
    thumbnail_url = Column(String(500))
    polygon_count = Column(Integer)
    file_size_kb = Column(Integer)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    queued_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_secs = Column(Integer)
