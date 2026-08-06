from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import ShopReturn, get_db
from ..dependencies import require_shop_editor
from ..shop_return_service import list_returns, resolve_return, return_to_dict

router = APIRouter(prefix="/api/shop-returns", tags=["shop-returns"])


class ShopReturnResolveRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=30)
    admin_note: str = Field(default="", max_length=2000)


@router.get("")
def admin_list_returns(
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_editor),
) -> dict:
    rows = list_returns(db, status=status)
    return {"returns": [return_to_dict(row, order) for row, order in rows]}


@router.get("/{return_id}")
def admin_get_return(
    return_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_shop_editor),
) -> dict:
    row = db.get(ShopReturn, return_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    from ..database import ShopOrder

    order = db.get(ShopOrder, row.order_id)
    return {"return": return_to_dict(row, order)}


@router.patch("/{return_id}")
def admin_resolve_return(
    return_id: str,
    payload: ShopReturnResolveRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_shop_editor),
) -> dict:
    row = db.get(ShopReturn, return_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    row = resolve_return(
        db,
        row,
        status=payload.status,
        admin_note=payload.admin_note,
        actor=user,
    )
    from ..database import ShopOrder

    order = db.get(ShopOrder, row.order_id)
    log_audit(
        db,
        entity_type="shop_return",
        entity_id=row.id,
        action=f"resolve_{row.status}",
        actor=user,
        details={"return_number": row.return_number, "status": row.status, "order_id": row.order_id},
    )
    return {"return": return_to_dict(row, order)}
