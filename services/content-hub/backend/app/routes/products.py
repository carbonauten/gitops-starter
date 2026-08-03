from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import Product, get_db
from ..dependencies import get_current_user, require_editor
from ..product_service import (
    list_products,
    to_admin_dict,
    unique_slug,
    validate_image_asset,
)
from ..schemas import ProductCreate, ProductResponse, ProductUpdate

router = APIRouter(prefix="/api/products", tags=["products"])


def _get_or_404(db: Session, product_id: str) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="not_found")
    return product


@router.get("")
def admin_list_products(
    q: Optional[str] = Query(default=None),
    published: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    products = list_products(db)
    if published is True:
        products = [item for item in products if item.is_published]
    elif published is False:
        products = [item for item in products if not item.is_published]
    if q:
        needle = q.strip().lower()
        products = [
            item
            for item in products
            if needle in item.name.lower()
            or needle in (item.sku or "").lower()
            or needle in (item.short_description or "").lower()
        ]
    return {"products": [ProductResponse(**to_admin_dict(item, db)) for item in products]}


@router.post("", status_code=201)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    validate_image_asset(db, payload.image_file_asset_id)
    slug = unique_slug(db, payload.slug or payload.name)
    product = Product(
        name=payload.name.strip(),
        slug=slug,
        short_description=payload.short_description.strip(),
        description=payload.description,
        price_cents=payload.price_cents,
        currency=(payload.currency or "EUR").upper(),
        sku=payload.sku.strip(),
        is_published=payload.is_published,
        sort_order=payload.sort_order,
        image_file_asset_id=payload.image_file_asset_id,
        stock_qty=payload.stock_qty,
        track_inventory=payload.track_inventory,
        vat_rate_bps=payload.vat_rate_bps,
        created_by_id=user["id"],
        created_by_name=user["name"],
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    log_audit(
        db,
        entity_type="product",
        entity_id=product.id,
        action="create",
        actor=user,
        details={"name": product.name, "slug": product.slug, "is_published": product.is_published},
    )
    return {"product": ProductResponse(**to_admin_dict(product, db))}


@router.get("/{product_id}")
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    product = _get_or_404(db, product_id)
    return {"product": ProductResponse(**to_admin_dict(product, db))}


@router.patch("/{product_id}")
def update_product(
    product_id: str,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    product = _get_or_404(db, product_id)
    data = payload.model_dump(exclude_unset=True)
    if "image_file_asset_id" in data:
        validate_image_asset(db, data["image_file_asset_id"])
        product.image_file_asset_id = data["image_file_asset_id"]
    if "name" in data and data["name"] is not None:
        product.name = data["name"].strip()
    if "slug" in data and data["slug"]:
        product.slug = unique_slug(db, data["slug"], exclude_id=product.id)
    if "short_description" in data and data["short_description"] is not None:
        product.short_description = data["short_description"].strip()
    if "description" in data and data["description"] is not None:
        product.description = data["description"]
    if "price_cents" in data and data["price_cents"] is not None:
        product.price_cents = data["price_cents"]
    if "currency" in data and data["currency"]:
        product.currency = data["currency"].upper()
    if "sku" in data and data["sku"] is not None:
        product.sku = data["sku"].strip()
    if "is_published" in data and data["is_published"] is not None:
        product.is_published = data["is_published"]
    if "sort_order" in data and data["sort_order"] is not None:
        product.sort_order = data["sort_order"]
    if "stock_qty" in data and data["stock_qty"] is not None:
        product.stock_qty = data["stock_qty"]
    if "track_inventory" in data and data["track_inventory"] is not None:
        product.track_inventory = data["track_inventory"]
    if "vat_rate_bps" in data and data["vat_rate_bps"] is not None:
        product.vat_rate_bps = data["vat_rate_bps"]
    db.commit()
    db.refresh(product)
    log_audit(
        db,
        entity_type="product",
        entity_id=product.id,
        action="update",
        actor=user,
        details={"name": product.name, "slug": product.slug, "is_published": product.is_published},
    )
    return {"product": ProductResponse(**to_admin_dict(product, db))}


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    product = _get_or_404(db, product_id)
    log_audit(
        db,
        entity_type="product",
        entity_id=product.id,
        action="delete",
        actor=user,
        details={"name": product.name, "slug": product.slug},
    )
    db.delete(product)
    db.commit()
    return Response(status_code=204)
