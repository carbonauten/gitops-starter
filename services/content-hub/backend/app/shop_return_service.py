"""Shop return / Gutschrift workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import ShopCreditLedger, ShopCustomer, ShopOrder, ShopReturn
from .email_service import send_plain_email
from .shop_order_service import get_order_items, restore_inventory

RETURN_REASONS = {"damaged", "wrong_item", "not_as_described", "changed_mind", "other"}
RETURN_STATUSES = {"requested", "approved", "rejected", "completed"}
OPEN_RETURN_STATUSES = {"requested", "approved"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_return_number(db: Session) -> str:
    today = _utc_now().strftime("%Y%m%d")
    prefix = f"RT-{today}-"
    count = (
        db.scalar(select(func.count()).select_from(ShopReturn).where(ShopReturn.return_number.like(f"{prefix}%")))
        or 0
    )
    return f"{prefix}{count + 1:04d}"


def return_to_dict(row: ShopReturn, order: ShopOrder | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": row.id,
        "return_number": row.return_number,
        "order_id": row.order_id,
        "customer_id": row.customer_id,
        "status": row.status,
        "reason": row.reason,
        "customer_note": row.customer_note,
        "admin_note": row.admin_note,
        "refund_method": row.refund_method,
        "credits_reversed": int(row.credits_reversed or 0),
        "inventory_restored": bool(row.inventory_restored),
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "resolved_by_name": row.resolved_by_name or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if order is not None:
        payload["order_number"] = order.order_number
        payload["order_status"] = order.status
        payload["order_total_cents"] = order.total_cents
        payload["order_currency"] = order.currency
        payload["customer_email"] = order.customer_email
        payload["customer_name"] = order.customer_name
        payload["credits_earned"] = int(order.credits_earned or 0)
    return payload


def _within_return_window(order: ShopOrder, settings: Settings) -> bool:
    window = max(1, int(settings.shop_return_window_days or 30))
    anchor = order.fulfilled_at or order.paid_at or order.created_at
    if not anchor:
        return False
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return _utc_now() <= anchor + timedelta(days=window)


def _active_return_for_order(db: Session, order_id: str) -> ShopReturn | None:
    return db.scalar(
        select(ShopReturn)
        .where(ShopReturn.order_id == order_id, ShopReturn.status.in_(tuple(OPEN_RETURN_STATUSES) + ("completed",)))
        .order_by(ShopReturn.created_at.desc())
        .limit(1)
    )


def request_return(
    db: Session,
    *,
    order: ShopOrder,
    customer_id: str,
    reason: str,
    customer_note: str = "",
) -> ShopReturn:
    settings = get_settings()
    if order.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="forbidden")
    existing = _active_return_for_order(db, order.id)
    if existing and existing.status in OPEN_RETURN_STATUSES:
        raise HTTPException(status_code=409, detail="return_already_open")
    if existing and existing.status == "completed":
        raise HTTPException(status_code=409, detail="return_already_completed")
    if order.status not in {"paid", "fulfilled"}:
        raise HTTPException(status_code=400, detail="return_not_allowed")
    if not _within_return_window(order, settings):
        raise HTTPException(status_code=400, detail="return_window_expired")

    cleaned_reason = (reason or "other").strip().lower()
    if cleaned_reason not in RETURN_REASONS:
        cleaned_reason = "other"

    row = ShopReturn(
        id=str(uuid4()),
        return_number=generate_return_number(db),
        order_id=order.id,
        customer_id=customer_id,
        status="requested",
        reason=cleaned_reason,
        customer_note=(customer_note or "").strip()[:2000],
        refund_method="credit_note",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    send_return_emails(db, row, order, event="requested")
    return row


def list_customer_returns(db: Session, customer_id: str) -> list[tuple[ShopReturn, ShopOrder | None]]:
    rows = list(
        db.scalars(
            select(ShopReturn).where(ShopReturn.customer_id == customer_id).order_by(ShopReturn.created_at.desc())
        ).all()
    )
    result: list[tuple[ShopReturn, ShopOrder | None]] = []
    for row in rows:
        result.append((row, db.get(ShopOrder, row.order_id)))
    return result


def list_returns(db: Session, *, status: Optional[str] = None) -> list[tuple[ShopReturn, ShopOrder | None]]:
    stmt = select(ShopReturn).order_by(ShopReturn.created_at.desc())
    if status:
        stmt = stmt.where(ShopReturn.status == status)
    rows = list(db.scalars(stmt).all())
    return [(row, db.get(ShopOrder, row.order_id)) for row in rows]


def _complete_return_side_effects(db: Session, row: ShopReturn, order: ShopOrder) -> None:
    items = get_order_items(db, order.id)
    if not row.inventory_restored:
        restore_inventory(db, items)
        row.inventory_restored = True

    credits = int(order.credits_earned or 0)
    if credits > 0 and int(row.credits_reversed or 0) == 0 and order.customer_id:
        customer = db.get(ShopCustomer, order.customer_id)
        available = int(customer.co2_credit_balance or 0) if customer else 0
        clawback = min(credits, available)
        if clawback > 0 and customer:
            customer.co2_credit_balance = available - clawback
            db.add(
                ShopCreditLedger(
                    id=str(uuid4()),
                    customer_id=customer.id,
                    order_id=order.id,
                    delta_credits=-clawback,
                    reason="return_clawback",
                    note=f"Retour {row.return_number} / {order.order_number}",
                )
            )
            row.credits_reversed = clawback
        else:
            row.credits_reversed = 0

    order.status = "returned"
    row.status = "completed"
    row.completed_at = _utc_now()
    if not row.resolved_at:
        row.resolved_at = row.completed_at
    db.commit()
    db.refresh(row)
    db.refresh(order)


def resolve_return(
    db: Session,
    row: ShopReturn,
    *,
    status: str,
    admin_note: str = "",
    actor: dict[str, Any] | None = None,
) -> ShopReturn:
    if status not in {"approved", "rejected", "completed"}:
        raise HTTPException(status_code=400, detail="validation")
    if row.status == "completed":
        raise HTTPException(status_code=409, detail="return_already_completed")
    if row.status == "rejected" and status != "rejected":
        raise HTTPException(status_code=409, detail="return_already_resolved")

    order = db.get(ShopOrder, row.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="not_found")

    actor = actor or {}
    row.admin_note = (admin_note or row.admin_note or "").strip()[:2000]
    row.resolved_by_id = actor.get("id") or actor.get("db_id") or ""
    row.resolved_by_name = actor.get("name") or ""

    if status == "rejected":
        row.status = "rejected"
        row.resolved_at = _utc_now()
        db.commit()
        db.refresh(row)
        send_return_emails(db, row, order, event="rejected")
        return row

    if status == "approved":
        row.status = "approved"
        row.resolved_at = _utc_now()
        db.commit()
        db.refresh(row)
        send_return_emails(db, row, order, event="approved")
        return row

    # completed — approve + stock + credit clawback in one step
    if row.status == "requested":
        row.status = "approved"
        row.resolved_at = _utc_now()
        db.commit()
        db.refresh(row)
    _complete_return_side_effects(db, row, order)
    send_return_emails(db, row, order, event="completed")
    return row


def send_return_emails(db: Session, row: ShopReturn, order: ShopOrder, *, event: str) -> None:
    settings = get_settings()
    labels = {
        "requested": "Retourenanfrage eingegangen",
        "approved": "Retourenanfrage genehmigt",
        "rejected": "Retourenanfrage abgelehnt",
        "completed": "Retoure abgeschlossen (Gutschrift / Lager)",
    }
    subject_label = labels.get(event, "Retoure")
    body = (
        f"Retoure {row.return_number}\n"
        f"Bestellung: {order.order_number}\n"
        f"Status: {row.status}\n"
        f"Grund: {row.reason}\n"
        f"Kundennotiz: {row.customer_note or '—'}\n"
        f"Admin-Notiz: {row.admin_note or '—'}\n"
        f"CO₂ zurückgebucht: {row.credits_reversed}\n"
        f"Lager wiederhergestellt: {'ja' if row.inventory_restored else 'nein'}\n\n"
        f"Hinweis: Geldrückerstattung erfolgt manuell (Gutschrift/Überweisung) durch den Shop.\n"
    )
    send_plain_email(
        to_email=order.customer_email,
        subject=f"{settings.shop_brand_name} {subject_label} {row.return_number}",
        body=body,
        settings=settings,
    )
    shop_inbox = settings.shop_contact
    if shop_inbox and shop_inbox.lower() != order.customer_email.lower():
        send_plain_email(
            to_email=shop_inbox,
            subject=f"Shop-Retoure {row.return_number} ({event})",
            body=body,
            settings=settings,
        )


def order_return_summary(db: Session, order_id: str) -> dict[str, Any] | None:
    row = db.scalar(
        select(ShopReturn).where(ShopReturn.order_id == order_id).order_by(ShopReturn.created_at.desc()).limit(1)
    )
    if not row:
        return None
    return return_to_dict(row)
