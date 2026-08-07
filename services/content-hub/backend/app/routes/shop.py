from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import FileAsset, get_db
from ..dependencies import require_it_master
from ..product_service import get_product_by_slug, list_products, to_public_dict
from ..schemas import ShopCheckoutRequest, ShopPageViewRequest, ShopProductPublic
from ..shop_analytics_service import monitoring_summary, record_page_view
from ..shop_bot_protection import client_ip, protect_shop_action
from ..shop_invoice_service import build_invoice_pdf, invoice_filename
from ..shop_order_service import (
    confirm_stripe_order,
    create_checkout_order,
    get_order_by_number,
    get_order_items,
    mark_order_paid,
    order_to_dict,
)
from ..storage import read_upload
from .shop_auth import get_optional_shop_customer

router = APIRouter(prefix="/api/shop", tags=["shop"])


@router.get("/config")
def shop_config() -> dict:
    settings = get_settings()
    return {
        "brand_name": settings.shop_brand_name,
        "company_name": settings.shop_company_name,
        "tagline": settings.shop_tagline,
        "contact_email": settings.shop_contact,
        "currency": settings.shop_currency,
        "hosts": settings.shop_hosts_list,
        "platform_url": settings.effective_public_origin or "https://app.carbonauten.com",
        "shipping_cents": settings.shop_shipping_cents,
        "free_shipping_from_cents": settings.shop_free_shipping_from_cents,
        "stripe_enabled": settings.shop_stripe_configured,
        "stripe_publishable_key": settings.shop_stripe_publishable_key,
        "invoice_enabled": True,
        "require_account_checkout": settings.shop_require_account_checkout,
        "co2_credits_per_euro": settings.shop_co2_credits_per_euro,
        "return_window_days": settings.shop_return_window_days,
        "analytics_enabled": settings.shop_analytics_enabled,
        "bot_protection": {
            "enabled": settings.shop_bot_protection_enabled,
            "turnstile_site_key": settings.shop_turnstile_site_key if settings.shop_turnstile_configured else "",
            "turnstile_required": settings.shop_turnstile_configured,
        },
        "bank": {
            "iban": settings.shop_bank_iban,
            "bic": settings.shop_bank_bic,
            "name": settings.shop_bank_name,
            "holder": settings.shop_bank_holder or settings.shop_brand_name,
        },
        "legal": {
            "impressum": settings.shop_impressum,
            "privacy": settings.shop_privacy,
            "terms": settings.shop_terms,
        },
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


@router.post("/checkout")
def shop_checkout(
    payload: ShopCheckoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    shop_customer: dict | None = Depends(get_optional_shop_customer),
) -> dict:
    settings = get_settings()
    protect_shop_action(
        request,
        bucket="shop_checkout",
        honeypot=payload.website,
        turnstile_token=payload.turnstile_token,
        limit=settings.shop_bot_checkout_rate_limit,
    )
    customer_payload = payload.customer.model_dump()
    if shop_customer:
        customer_payload["email"] = shop_customer["email"]
        if not (customer_payload.get("name") or "").strip():
            customer_payload["name"] = shop_customer["name"]
    order, items, checkout_url = create_checkout_order(
        db,
        items=[item.model_dump() for item in payload.items],
        customer=customer_payload,
        payment_method=payload.payment_method,
        notes=payload.notes,
        customer_id=shop_customer["id"] if shop_customer else None,
    )
    return {
        "order": order_to_dict(order, items, include_token=True),
        "checkout_url": checkout_url,
    }


@router.post("/analytics/pageview")
def shop_record_pageview(
    payload: ShopPageViewRequest,
    request: Request,
    db: Session = Depends(get_db),
    shop_customer: dict | None = Depends(get_optional_shop_customer),
) -> dict:
    settings = get_settings()
    if not settings.shop_analytics_enabled:
        return {"ok": True, "recorded": False}
    protect_shop_action(
        request,
        bucket="shop_pageview",
        honeypot=payload.website,
        limit=settings.shop_bot_pageview_rate_limit,
        window_seconds=60,
    )
    record_page_view(
        db,
        path=payload.path,
        referrer=payload.referrer,
        session_id=payload.session_id,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        customer_id=shop_customer["id"] if shop_customer else None,
    )
    return {"ok": True, "recorded": True}


@router.get("/monitoring/summary")
def shop_monitoring_summary(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return monitoring_summary(db, days=days)


@router.get("/orders/{order_number}")
def shop_get_order(
    order_number: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    order = get_order_by_number(db, order_number)
    if not order or order.access_token != token:
        raise HTTPException(status_code=404, detail="not_found")
    return {"order": order_to_dict(order, get_order_items(db, order.id), include_token=True)}


@router.get("/orders/{order_number}/invoice.pdf")
def shop_download_invoice(
    order_number: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    order = get_order_by_number(db, order_number)
    if not order or order.access_token != token:
        raise HTTPException(status_code=404, detail="not_found")
    pdf = build_invoice_pdf(order, get_order_items(db, order.id))
    filename = invoice_filename(order)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/orders/{order_number}/confirm")
def shop_confirm_order(
    order_number: str,
    token: str = Query(...),
    session_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    if not session_id:
        raise HTTPException(status_code=400, detail="validation")
    order = confirm_stripe_order(db, order_number=order_number, access_token=token, session_id=session_id)
    return {"order": order_to_dict(order, get_order_items(db, order.id), include_token=True)}


@router.post("/stripe/webhook")
async def shop_stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    payload = await request.json()
    event_type = payload.get("type")
    data_object = (payload.get("data") or {}).get("object") or {}
    if event_type == "checkout.session.completed":
        order_id = (data_object.get("metadata") or {}).get("order_id")
        order_number = (data_object.get("metadata") or {}).get("order_number")
        order = None
        if order_id:
            from ..database import ShopOrder

            order = db.get(ShopOrder, order_id)
        if order is None and order_number:
            order = get_order_by_number(db, order_number)
        if order:
            payment_intent = data_object.get("payment_intent") or ""
            if isinstance(payment_intent, dict):
                payment_intent = payment_intent.get("id") or ""
            mark_order_paid(db, order, payment_intent=str(payment_intent or ""))
    # Optional: verify signature when webhook secret is set (basic presence check)
    _ = settings.shop_stripe_webhook_secret
    return {"received": True}
