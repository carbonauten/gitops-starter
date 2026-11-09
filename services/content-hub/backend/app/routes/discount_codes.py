from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_shop_access, require_shop_editor
from ..discount_code_service import (
    create_discount_code,
    delete_discount_code,
    get_discount_code_row,
    list_discount_codes,
    to_dict,
    update_discount_code,
)
from ..schemas import DiscountCodeCreate, DiscountCodeUpdate

router = APIRouter(prefix="/api/discount-codes", tags=["discount-codes"])


@router.get("")
def admin_list_discount_codes(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_access),
) -> dict:
    return {"discount_codes": [to_dict(row) for row in list_discount_codes(db)]}


@router.post("", status_code=201)
def admin_create_discount_code(
    payload: DiscountCodeCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_shop_editor),
) -> dict:
    row = create_discount_code(
        db,
        code=payload.code,
        discount_type=payload.discount_type,
        percent_off_bps=payload.percent_off_bps,
        amount_off_cents=payload.amount_off_cents,
        min_order_cents=payload.min_order_cents,
        max_redemptions=payload.max_redemptions,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        actor=user,
    )
    log_audit(
        db,
        entity_type="discount_code",
        entity_id=row.id,
        action="create",
        actor=user,
        details={"code": row.code, "discount_type": row.discount_type},
    )
    return {"discount_code": to_dict(row)}


@router.patch("/{code_id}")
def admin_update_discount_code(
    code_id: str,
    payload: DiscountCodeUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_shop_editor),
) -> dict:
    row = update_discount_code(
        db,
        code_id,
        is_active=payload.is_active,
        min_order_cents=payload.min_order_cents,
        max_redemptions=payload.max_redemptions,
        clear_max_redemptions=payload.clear_max_redemptions,
        valid_from=payload.valid_from,
        clear_valid_from=payload.clear_valid_from,
        valid_until=payload.valid_until,
        clear_valid_until=payload.clear_valid_until,
    )
    log_audit(
        db,
        entity_type="discount_code",
        entity_id=row.id,
        action="update",
        actor=user,
        details={"code": row.code, "is_active": row.is_active},
    )
    return {"discount_code": to_dict(row)}


@router.delete("/{code_id}", status_code=204)
def admin_delete_discount_code(
    code_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_shop_editor),
):
    row = get_discount_code_row(db, code_id)
    log_audit(db, entity_type="discount_code", entity_id=row.id, action="delete", actor=user, details={"code": row.code})
    delete_discount_code(db, code_id)
    return Response(status_code=204)
