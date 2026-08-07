from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import ShopOrder, get_db
from ..dependencies import require_shop_editor
from ..shop_invoice_service import build_invoice_pdf, invoice_filename
from ..shop_order_service import get_order_items, list_orders, order_to_dict, update_order_status

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=30)
    shipping_carrier: str = Field(default="", max_length=80)
    tracking_number: str = Field(default="", max_length=120)
    tracking_url: str = Field(default="", max_length=500)


@router.get("")
def admin_list_orders(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_editor),
) -> dict:
    orders = list_orders(db, status=status)
    return {
        "orders": [order_to_dict(order, get_order_items(db, order.id)) for order in orders],
    }


@router.get("/{order_id}")
def admin_get_order(
    order_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_editor),
) -> dict:
    order = db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="not_found")
    return {"order": order_to_dict(order, get_order_items(db, order.id))}


@router.get("/{order_id}/invoice.pdf")
def admin_download_invoice(
    order_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_editor),
) -> Response:
    order = db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="not_found")
    pdf = build_invoice_pdf(order, get_order_items(db, order.id))
    filename = invoice_filename(order)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{order_id}")
def admin_update_order(
    order_id: str,
    payload: OrderStatusUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_shop_editor),
) -> dict:
    order = db.get(ShopOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="not_found")
    shipping_kwargs = {}
    if payload.status == "fulfilled" or payload.shipping_carrier or payload.tracking_number or payload.tracking_url:
        shipping_kwargs = {
            "shipping_carrier": payload.shipping_carrier,
            "tracking_number": payload.tracking_number,
            "tracking_url": payload.tracking_url,
        }
    order = update_order_status(db, order, payload.status, **shipping_kwargs)
    log_audit(
        db,
        entity_type="shop_order",
        entity_id=order.id,
        action="update_status",
        actor=user,
        details={
            "order_number": order.order_number,
            "status": order.status,
            "shipping_carrier": order.shipping_carrier,
            "tracking_number": order.tracking_number,
        },
    )
    return {"order": order_to_dict(order, get_order_items(db, order.id))}
