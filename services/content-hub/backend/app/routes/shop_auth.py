from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import clear_shop_session, get_shop_session, set_shop_session
from ..config import get_settings
from ..database import get_db
from ..shop_bot_protection import protect_shop_action
from ..shop_customer_service import (
    authenticate_customer,
    customer_to_dict,
    get_customer,
    list_customer_ledger,
    list_customer_orders,
    register_customer,
)
from ..shop_order_service import get_order_items, order_to_dict

router = APIRouter(prefix="/api/shop/auth", tags=["shop-auth"])


class ShopRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    language: str | None = None
    website: str = ""  # honeypot
    turnstile_token: str = ""


class ShopLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)
    website: str = ""  # honeypot
    turnstile_token: str = ""


def get_current_shop_customer(request: Request, db: Session = Depends(get_db)) -> dict:
    session = get_shop_session(request)
    if not session or "customer" not in session:
        raise HTTPException(status_code=401, detail="unauthorized")
    customer_id = (session.get("customer") or {}).get("id")
    if not customer_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    customer = get_customer(db, customer_id)
    if not customer or not customer.is_active:
        raise HTTPException(status_code=401, detail="unauthorized")
    return customer_to_dict(customer)


def get_optional_shop_customer(request: Request, db: Session = Depends(get_db)) -> dict | None:
    session = get_shop_session(request)
    if not session or "customer" not in session:
        return None
    customer_id = (session.get("customer") or {}).get("id")
    if not customer_id:
        return None
    customer = get_customer(db, customer_id)
    if not customer or not customer.is_active:
        return None
    return customer_to_dict(customer)


@router.post("/register")
def shop_register(
    payload: ShopRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    protect_shop_action(
        request,
        bucket="shop_register",
        honeypot=payload.website,
        turnstile_token=payload.turnstile_token,
        limit=settings.shop_bot_auth_rate_limit,
    )
    customer = register_customer(
        db,
        email=payload.email,
        name=payload.name,
        password=payload.password,
        language=payload.language,
    )
    data = customer_to_dict(customer)
    set_shop_session(response, {"customer": data})
    return {"customer": data}


@router.post("/login")
def shop_login(
    payload: ShopLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    protect_shop_action(
        request,
        bucket="shop_login",
        honeypot=payload.website,
        turnstile_token=payload.turnstile_token,
        limit=settings.shop_bot_auth_rate_limit,
    )
    customer = authenticate_customer(db, payload.email, payload.password)
    data = customer_to_dict(customer)
    set_shop_session(response, {"customer": data})
    return {"customer": data}


@router.post("/logout")
def shop_logout(response: Response) -> dict:
    clear_shop_session(response)
    return {"ok": True}


@router.get("/me")
def shop_me(customer: dict = Depends(get_current_shop_customer)) -> dict:
    return {"customer": customer}


@router.get("/me/credits")
def shop_my_credits(
    db: Session = Depends(get_db),
    customer: dict = Depends(get_current_shop_customer),
) -> dict:
    return {
        "balance": customer["co2_credit_balance"],
        "ledger": list_customer_ledger(db, customer["id"]),
    }


@router.get("/me/orders")
def shop_my_orders(
    db: Session = Depends(get_db),
    customer: dict = Depends(get_current_shop_customer),
) -> dict:
    orders = list_customer_orders(db, customer["id"])
    return {"orders": [order_to_dict(order, get_order_items(db, order.id)) for order in orders]}
