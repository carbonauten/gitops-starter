from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import ShopCreditLedger, ShopCustomer, ShopOrder
from .i18n import normalize_language
from .password_service import hash_password, verify_password


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def customer_to_dict(customer: ShopCustomer) -> dict[str, Any]:
    return {
        "id": customer.id,
        "email": customer.email,
        "name": customer.name,
        "language": customer.language,
        "is_active": customer.is_active,
        "co2_credit_balance": int(customer.co2_credit_balance or 0),
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "last_login_at": customer.last_login_at.isoformat() if customer.last_login_at else None,
    }


def get_customer_by_email(db: Session, email: str) -> ShopCustomer | None:
    return db.scalar(select(ShopCustomer).where(ShopCustomer.email == email.strip().lower()))


def get_customer(db: Session, customer_id: str) -> ShopCustomer | None:
    return db.get(ShopCustomer, customer_id)


def register_customer(
    db: Session,
    *,
    email: str,
    name: str,
    password: str,
    language: str | None = None,
) -> ShopCustomer:
    settings = get_settings()
    normalized_email = email.strip().lower()
    normalized_name = name.strip()
    if not normalized_email or "@" not in normalized_email or not normalized_name or len(password) < 8:
        raise HTTPException(status_code=422, detail="validation")
    if get_customer_by_email(db, normalized_email):
        raise HTTPException(status_code=409, detail="user_exists")

    customer = ShopCustomer(
        id=str(uuid4()),
        email=normalized_email,
        name=normalized_name,
        password_hash=hash_password(password),
        language=normalize_language(language or settings.default_language),
        is_active=True,
        co2_credit_balance=0,
        last_login_at=_utc_now(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def ensure_initial_shop_admin(db: Session) -> None:
    """Mirror platform INITIAL_ADMIN_* into a shop customer account (same email/password)."""
    settings = get_settings()
    email = (settings.shop_admin_email or settings.initial_admin_email).strip().lower()
    password = (settings.shop_admin_password or settings.initial_admin_password).strip()
    if not email or not password:
        return

    display_name = (
        settings.shop_admin_name.strip()
        or settings.initial_admin_name.strip()
        or email.split("@", 1)[0].replace(".", " ").title()
    )
    customer = get_customer_by_email(db, email)
    if customer is None:
        customer = ShopCustomer(
            id=str(uuid4()),
            email=email,
            name=display_name,
            password_hash=hash_password(password),
            language=normalize_language(settings.default_language),
            is_active=True,
            co2_credit_balance=0,
        )
        db.add(customer)
    else:
        customer.password_hash = hash_password(password)
        customer.name = display_name or customer.name
        customer.is_active = True
    db.commit()


def _sync_platform_user_to_shop_customer(db: Session, platform_user, customer: ShopCustomer | None) -> ShopCustomer:
    settings = get_settings()
    if not platform_user.password_hash:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if customer is None:
        customer = ShopCustomer(
            id=str(uuid4()),
            email=platform_user.email.strip().lower(),
            name=platform_user.name,
            password_hash=platform_user.password_hash,
            language=platform_user.language or settings.default_language,
            is_active=True,
            co2_credit_balance=0,
        )
        db.add(customer)
    else:
        customer.password_hash = platform_user.password_hash
        customer.name = platform_user.name or customer.name
        customer.is_active = True
    customer.last_login_at = _utc_now()
    db.commit()
    db.refresh(customer)
    return customer


def authenticate_customer(db: Session, email: str, password: str) -> ShopCustomer:
    normalized_email = email.strip().lower()
    customer = get_customer_by_email(db, normalized_email)

    # Any active platform employee can use the same email/password in the shop.
    if customer is None or not verify_password(password, customer.password_hash):
        from .user_service import get_user_by_email

        platform_user = get_user_by_email(db, normalized_email)
        if (
            platform_user
            and platform_user.is_active
            and platform_user.password_hash
            and verify_password(password, platform_user.password_hash)
        ):
            return _sync_platform_user_to_shop_customer(db, platform_user, customer)

    if not customer or not customer.password_hash:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not customer.is_active:
        raise HTTPException(status_code=403, detail="account_disabled")
    if not verify_password(password, customer.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    customer.last_login_at = _utc_now()
    db.commit()
    db.refresh(customer)
    return customer


def list_customers(db: Session) -> list[ShopCustomer]:
    return list(db.scalars(select(ShopCustomer).order_by(ShopCustomer.created_at.desc())).all())


def update_customer_active(db: Session, customer_id: str, is_active: bool) -> ShopCustomer:
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="not_found")
    customer.is_active = is_active
    db.commit()
    db.refresh(customer)
    return customer


def adjust_customer_credits(
    db: Session,
    customer_id: str,
    *,
    delta: int,
    note: str = "",
    reason: str = "adjust",
    order_id: str | None = None,
    allow_floor_zero: bool = False,
) -> ShopCustomer:
    customer = get_customer(db, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="not_found")
    if delta == 0:
        return customer
    new_balance = int(customer.co2_credit_balance or 0) + int(delta)
    if new_balance < 0:
        if allow_floor_zero:
            delta = -int(customer.co2_credit_balance or 0)
            new_balance = 0
            if delta == 0:
                return customer
        else:
            raise HTTPException(status_code=400, detail="insufficient_credits")
    customer.co2_credit_balance = new_balance
    db.add(
        ShopCreditLedger(
            id=str(uuid4()),
            customer_id=customer.id,
            order_id=order_id,
            delta_credits=int(delta),
            reason=reason,
            note=(note or "").strip()[:500],
        )
    )
    db.commit()
    db.refresh(customer)
    return customer


def compute_order_credits(order: ShopOrder, settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    per_euro = max(0, int(settings.shop_co2_credits_per_euro or 0))
    if per_euro <= 0:
        return 0
    euros = max(0, int(order.total_cents or 0)) // 100
    return euros * per_euro


def award_co2_credits_for_order(db: Session, order: ShopOrder, *, settings: Settings | None = None) -> int:
    """Idempotent: awards credits once when order is paid and linked to a customer."""
    settings = settings or get_settings()
    if order.credits_awarded_at:
        return int(order.credits_earned or 0)
    if not order.customer_id:
        return 0
    if order.status not in {"paid", "fulfilled"}:
        return 0

    credits = compute_order_credits(order, settings)
    order.credits_earned = credits
    order.credits_awarded_at = _utc_now()
    if credits <= 0:
        db.commit()
        db.refresh(order)
        return 0

    customer = get_customer(db, order.customer_id)
    if not customer or not customer.is_active:
        db.commit()
        db.refresh(order)
        return 0

    customer.co2_credit_balance = int(customer.co2_credit_balance or 0) + credits
    db.add(
        ShopCreditLedger(
            id=str(uuid4()),
            customer_id=customer.id,
            order_id=order.id,
            delta_credits=credits,
            reason="order_paid",
            note=f"Order {order.order_number}",
        )
    )
    db.commit()
    db.refresh(order)
    return credits


def list_customer_ledger(db: Session, customer_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = list(
        db.scalars(
            select(ShopCreditLedger)
            .where(ShopCreditLedger.customer_id == customer_id)
            .order_by(ShopCreditLedger.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "delta_credits": row.delta_credits,
            "reason": row.reason,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def list_customer_orders(db: Session, customer_id: str) -> list[ShopOrder]:
    return list(
        db.scalars(
            select(ShopOrder).where(ShopOrder.customer_id == customer_id).order_by(ShopOrder.created_at.desc())
        ).all()
    )
