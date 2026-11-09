from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import DiscountCode


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_code(raw: str) -> str:
    return (raw or "").strip().upper()


def to_dict(code: DiscountCode) -> dict[str, Any]:
    return {
        "id": code.id,
        "code": code.code,
        "discount_type": code.discount_type,
        "percent_off_bps": code.percent_off_bps,
        "amount_off_cents": code.amount_off_cents,
        "min_order_cents": code.min_order_cents,
        "max_redemptions": code.max_redemptions,
        "redemption_count": code.redemption_count,
        "valid_from": code.valid_from.isoformat() if code.valid_from else None,
        "valid_until": code.valid_until.isoformat() if code.valid_until else None,
        "is_active": code.is_active,
        "created_by_name": code.created_by_name,
        "created_at": code.created_at.isoformat() if code.created_at else None,
    }


def list_discount_codes(db: Session) -> list[DiscountCode]:
    return list(db.scalars(select(DiscountCode).order_by(DiscountCode.created_at.desc())).all())


def get_discount_code_row(db: Session, code_id: str) -> DiscountCode:
    row = db.get(DiscountCode, code_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return row


def _validate_value_fields(
    discount_type: str, percent_off_bps: Optional[int], amount_off_cents: Optional[int]
) -> None:
    if discount_type == "percent":
        if not percent_off_bps or percent_off_bps <= 0 or percent_off_bps > 10000:
            raise HTTPException(status_code=400, detail="validation")
    elif discount_type == "fixed":
        if not amount_off_cents or amount_off_cents <= 0:
            raise HTTPException(status_code=400, detail="validation")
    else:
        raise HTTPException(status_code=400, detail="validation")


def create_discount_code(
    db: Session,
    *,
    code: str,
    discount_type: str,
    percent_off_bps: Optional[int],
    amount_off_cents: Optional[int],
    min_order_cents: int,
    max_redemptions: Optional[int],
    valid_from: Optional[datetime],
    valid_until: Optional[datetime],
    actor: dict[str, Any],
) -> DiscountCode:
    normalized = _normalize_code(code)
    if not normalized:
        raise HTTPException(status_code=400, detail="validation")
    discount_type = (discount_type or "").strip().lower()
    _validate_value_fields(discount_type, percent_off_bps, amount_off_cents)
    if db.scalar(select(DiscountCode).where(DiscountCode.code == normalized)):
        raise HTTPException(status_code=409, detail="discount_code_already_exists")

    row = DiscountCode(
        id=str(uuid4()),
        code=normalized,
        discount_type=discount_type,
        percent_off_bps=percent_off_bps if discount_type == "percent" else None,
        amount_off_cents=amount_off_cents if discount_type == "fixed" else None,
        min_order_cents=max(0, int(min_order_cents or 0)),
        max_redemptions=max_redemptions,
        valid_from=valid_from,
        valid_until=valid_until,
        is_active=True,
        created_by_id=str(actor.get("id") or actor.get("db_id") or ""),
        created_by_name=str(actor.get("name") or ""),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_discount_code(
    db: Session,
    code_id: str,
    *,
    is_active: Optional[bool] = None,
    min_order_cents: Optional[int] = None,
    max_redemptions: Optional[int] = None,
    valid_from: Optional[datetime] = None,
    valid_until: Optional[datetime] = None,
    clear_valid_from: bool = False,
    clear_valid_until: bool = False,
    clear_max_redemptions: bool = False,
) -> DiscountCode:
    row = get_discount_code_row(db, code_id)
    if is_active is not None:
        row.is_active = is_active
    if min_order_cents is not None:
        row.min_order_cents = max(0, int(min_order_cents))
    if clear_max_redemptions:
        row.max_redemptions = None
    elif max_redemptions is not None:
        row.max_redemptions = max_redemptions
    if clear_valid_from:
        row.valid_from = None
    elif valid_from is not None:
        row.valid_from = valid_from
    if clear_valid_until:
        row.valid_until = None
    elif valid_until is not None:
        row.valid_until = valid_until
    db.commit()
    db.refresh(row)
    return row


def delete_discount_code(db: Session, code_id: str) -> None:
    row = get_discount_code_row(db, code_id)
    db.delete(row)
    db.commit()


def compute_discount_cents(code: DiscountCode, subtotal_cents: int) -> int:
    if code.discount_type == "percent":
        amount = (subtotal_cents * (code.percent_off_bps or 0)) // 10000
    else:
        amount = code.amount_off_cents or 0
    return max(0, min(amount, subtotal_cents))


def resolve_and_validate_discount(db: Session, *, code: str, subtotal_cents: int) -> DiscountCode:
    """Raises a specific, translatable error for every rejection reason -
    a generic "invalid code" would leave a customer unable to tell a typo
    apart from an expired or not-yet-met-minimum code."""
    normalized = _normalize_code(code)
    row = db.scalar(select(DiscountCode).where(DiscountCode.code == normalized))
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="discount_code_invalid")
    now = _utc_now()
    # SQLite round-trips DateTime(timezone=True) values as naive datetimes
    # even though they were stored as UTC-aware - normalize before comparing,
    # or this raises instead of validating on sqlite (dev/test) specifically.
    valid_from = row.valid_from.replace(tzinfo=timezone.utc) if row.valid_from and row.valid_from.tzinfo is None else row.valid_from
    valid_until = row.valid_until.replace(tzinfo=timezone.utc) if row.valid_until and row.valid_until.tzinfo is None else row.valid_until
    if valid_from and now < valid_from:
        raise HTTPException(status_code=400, detail="discount_code_not_yet_valid")
    if valid_until and now > valid_until:
        raise HTTPException(status_code=400, detail="discount_code_expired")
    if row.max_redemptions is not None and row.redemption_count >= row.max_redemptions:
        raise HTTPException(status_code=400, detail="discount_code_limit_reached")
    if row.min_order_cents and subtotal_cents < row.min_order_cents:
        raise HTTPException(status_code=400, detail="discount_code_minimum_not_met")
    return row


def record_redemption(db: Session, code: DiscountCode) -> None:
    code.redemption_count = int(code.redemption_count or 0) + 1


def release_redemption(db: Session, code_value: str) -> None:
    """Called when an order using this code is cancelled, mirroring
    restore_inventory() - frees up the redemption slot again. Silently
    no-ops if the code was deleted since the order was placed."""
    if not code_value:
        return
    row = db.scalar(select(DiscountCode).where(DiscountCode.code == _normalize_code(code_value)))
    if row and row.redemption_count > 0:
        row.redemption_count -= 1
