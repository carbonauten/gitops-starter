from __future__ import annotations

import re
import unicodedata
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import FileAsset, Product


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "product"


def unique_slug(db: Session, base: str, *, exclude_id: Optional[str] = None) -> str:
    candidate = slugify(base)[:180]
    index = 2
    while True:
        stmt = select(Product).where(Product.slug == candidate)
        existing = db.scalar(stmt)
        if existing is None or (exclude_id and existing.id == exclude_id):
            return candidate
        candidate = f"{slugify(base)[:170]}-{index}"
        index += 1


def validate_image_asset(db: Session, file_asset_id: Optional[str]) -> None:
    if not file_asset_id:
        return
    if not db.get(FileAsset, file_asset_id):
        raise HTTPException(status_code=404, detail="not_found")


def image_name(db: Session, file_asset_id: Optional[str]) -> Optional[str]:
    if not file_asset_id:
        return None
    asset = db.get(FileAsset, file_asset_id)
    return asset.original_name if asset else None


def product_image_url(slug: str, file_asset_id: Optional[str]) -> Optional[str]:
    if not file_asset_id:
        return None
    return f"/api/shop/products/{slug}/image"


def to_admin_dict(product: Product, db: Session) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "short_description": product.short_description,
        "description": product.description,
        "price_cents": product.price_cents,
        "currency": product.currency,
        "sku": product.sku,
        "is_published": product.is_published,
        "sort_order": product.sort_order,
        "image_file_asset_id": product.image_file_asset_id,
        "image_name": image_name(db, product.image_file_asset_id),
        "image_url": product_image_url(product.slug, product.image_file_asset_id),
        "created_by_id": product.created_by_id,
        "created_by_name": product.created_by_name,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def to_public_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "short_description": product.short_description,
        "description": product.description,
        "price_cents": product.price_cents,
        "currency": product.currency,
        "sku": product.sku,
        "image_url": product_image_url(product.slug, product.image_file_asset_id),
        "sort_order": product.sort_order,
    }


def list_products(db: Session, *, published_only: bool = False) -> list[Product]:
    stmt = select(Product).order_by(Product.sort_order.asc(), Product.created_at.desc())
    if published_only:
        stmt = stmt.where(Product.is_published.is_(True))
    return list(db.scalars(stmt).all())


def get_product_by_slug(db: Session, slug: str, *, published_only: bool = False) -> Product | None:
    stmt = select(Product).where(Product.slug == slug)
    if published_only:
        stmt = stmt.where(Product.is_published.is_(True))
    return db.scalar(stmt)


def count_products(db: Session, *, published_only: bool = False) -> int:
    stmt = select(func.count()).select_from(Product)
    if published_only:
        stmt = stmt.where(Product.is_published.is_(True))
    return int(db.scalar(stmt) or 0)
