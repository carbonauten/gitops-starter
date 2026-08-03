from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import FileAsset, get_db
from ..product_service import get_product_by_slug, list_products, to_public_dict
from ..schemas import ShopProductPublic
from ..storage import read_upload

router = APIRouter(prefix="/api/shop", tags=["shop"])


@router.get("/config")
def shop_config() -> dict:
    settings = get_settings()
    return {
        "brand_name": settings.shop_brand_name,
        "tagline": settings.shop_tagline,
        "contact_email": settings.shop_contact,
        "currency": settings.shop_currency,
        "hosts": settings.shop_hosts_list,
        "platform_url": settings.effective_public_origin or "https://app.carbonauten.com",
    }


@router.get("/products")
def public_list_products(db: Session = Depends(get_db)) -> dict:
    products = list_products(db, published_only=True)
    return {"products": [ShopProductPublic(**to_public_dict(item)) for item in products]}


@router.get("/products/{slug}")
def public_get_product(slug: str, db: Session = Depends(get_db)) -> dict:
    product = get_product_by_slug(db, slug, published_only=True)
    if not product:
        raise HTTPException(status_code=404, detail="not_found")
    return {"product": ShopProductPublic(**to_public_dict(product))}


@router.get("/products/{slug}/image")
def public_product_image(slug: str, db: Session = Depends(get_db)):
    product = get_product_by_slug(db, slug, published_only=True)
    if not product or not product.image_file_asset_id:
        raise HTTPException(status_code=404, detail="not_found")
    file_asset = db.get(FileAsset, product.image_file_asset_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    if file_asset.storage_path.startswith("oss://"):
        content = read_upload(file_asset.storage_path)
        return StreamingResponse(
            iter([content]),
            media_type=file_asset.content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )
    path = Path(file_asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(
        path,
        media_type=file_asset.content_type,
        filename=file_asset.original_name,
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=3600"},
    )
