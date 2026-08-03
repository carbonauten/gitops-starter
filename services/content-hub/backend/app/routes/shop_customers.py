from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_it_master, require_shop_access
from ..shop_customer_service import (
    adjust_customer_credits,
    customer_to_dict,
    get_customer,
    list_customer_ledger,
    list_customer_orders,
    list_customers,
    update_customer_active,
)
from ..shop_order_service import get_order_items, order_to_dict

router = APIRouter(prefix="/api/shop-customers", tags=["shop-customers"])


class ActiveUpdate(BaseModel):
    is_active: bool


class CreditsAdjust(BaseModel):
    delta: int
    note: str = Field(default="", max_length=500)


@router.get("")
def admin_list_shop_customers(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_access),
) -> dict:
    return {"customers": [customer_to_dict(item) for item in list_customers(db)]}


@router.get("/{customer_id}")
def admin_get_shop_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_access),
) -> dict:
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="not_found")
    return {
        "customer": customer_to_dict(customer),
        "ledger": list_customer_ledger(db, customer_id),
        "orders": [
            order_to_dict(order, get_order_items(db, order.id))
            for order in list_customer_orders(db, customer_id)
        ],
    }


@router.patch("/{customer_id}/active")
def admin_set_shop_customer_active(
    customer_id: str,
    payload: ActiveUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    customer = update_customer_active(db, customer_id, payload.is_active)
    return {"customer": customer_to_dict(customer)}


@router.post("/{customer_id}/credits")
def admin_adjust_shop_customer_credits(
    customer_id: str,
    payload: CreditsAdjust,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    customer = adjust_customer_credits(db, customer_id, delta=payload.delta, note=payload.note)
    return {"customer": customer_to_dict(customer)}
