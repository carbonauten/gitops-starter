from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Product, ShopOrder, ShopOrderItem
from .email_service import send_plain_email

logger = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_order_number(db: Session) -> str:
    today = _utc_now().strftime("%Y%m%d")
    prefix = f"FC-{today}-"
    count = (
        db.scalar(select(func.count()).select_from(ShopOrder).where(ShopOrder.order_number.like(f"{prefix}%"))) or 0
    )
    return f"{prefix}{count + 1:04d}"


def product_available_qty(product: Product) -> Optional[int]:
    if not product.track_inventory:
        return None
    return max(0, int(product.stock_qty or 0))


def assert_stock_available(product: Product, quantity: int) -> None:
    if quantity < 1:
        raise HTTPException(status_code=400, detail="validation")
    if not product.is_published:
        raise HTTPException(status_code=400, detail="product_unavailable")
    if product.track_inventory and product.stock_qty < quantity:
        raise HTTPException(status_code=409, detail="out_of_stock")


def compute_shipping_cents(settings: Settings, subtotal_cents: int) -> int:
    free_from = max(0, int(settings.shop_free_shipping_from_cents or 0))
    shipping = max(0, int(settings.shop_shipping_cents or 0))
    if free_from > 0 and subtotal_cents >= free_from:
        return 0
    return shipping


def compute_vat_from_gross(gross_cents: int, vat_rate_bps: int) -> int:
    """Prices are gross (inkl. MwSt). Extract VAT portion."""
    if vat_rate_bps <= 0 or gross_cents <= 0:
        return 0
    return int(round(gross_cents - (gross_cents * 10000) / (10000 + vat_rate_bps)))


def order_to_dict(order: ShopOrder, items: list[ShopOrderItem], *, include_token: bool = False) -> dict[str, Any]:
    payload = {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_method": order.payment_method,
        "currency": order.currency,
        "subtotal_cents": order.subtotal_cents,
        "shipping_cents": order.shipping_cents,
        "vat_cents": order.vat_cents,
        "total_cents": order.total_cents,
        "customer_email": order.customer_email,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "company": order.company,
        "address_line1": order.address_line1,
        "address_line2": order.address_line2,
        "postal_code": order.postal_code,
        "city": order.city,
        "country": order.country,
        "notes": order.notes,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "fulfilled_at": order.fulfilled_at.isoformat() if order.fulfilled_at else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "product_sku": item.product_sku,
                "unit_price_cents": item.unit_price_cents,
                "vat_rate_bps": item.vat_rate_bps,
                "quantity": item.quantity,
                "line_total_cents": item.line_total_cents,
            }
            for item in items
        ],
    }
    if include_token:
        payload["access_token"] = order.access_token
    return payload


def get_order_items(db: Session, order_id: str) -> list[ShopOrderItem]:
    return list(db.scalars(select(ShopOrderItem).where(ShopOrderItem.order_id == order_id)).all())


def get_order_by_number(db: Session, order_number: str) -> ShopOrder | None:
    return db.scalar(select(ShopOrder).where(ShopOrder.order_number == order_number))


def create_checkout_order(
    db: Session,
    *,
    items: list[dict[str, Any]],
    customer: dict[str, Any],
    payment_method: str,
    notes: str = "",
    settings: Settings | None = None,
) -> tuple[ShopOrder, list[ShopOrderItem], Optional[str]]:
    settings = settings or get_settings()
    payment_method = (payment_method or "stripe").strip().lower()
    if payment_method not in {"stripe", "invoice"}:
        raise HTTPException(status_code=400, detail="validation")
    if payment_method == "stripe" and not settings.shop_stripe_configured:
        # Fall back to invoice when Stripe is not configured yet
        payment_method = "invoice"

    if not items:
        raise HTTPException(status_code=400, detail="empty_cart")

    email = (customer.get("email") or "").strip().lower()
    name = (customer.get("name") or "").strip()
    if not email or "@" not in email or not name:
        raise HTTPException(status_code=400, detail="validation")

    resolved_lines: list[tuple[Product, int]] = []
    for raw in items:
        product_id = str(raw.get("product_id") or "")
        quantity = int(raw.get("quantity") or 0)
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="not_found")
        assert_stock_available(product, quantity)
        resolved_lines.append((product, quantity))

    subtotal = 0
    vat_total = 0
    order_items: list[ShopOrderItem] = []
    for product, quantity in resolved_lines:
        line_total = product.price_cents * quantity
        subtotal += line_total
        vat_total += compute_vat_from_gross(line_total, product.vat_rate_bps or 1900)
        order_items.append(
            ShopOrderItem(
                id=str(uuid4()),
                order_id="",  # set after order id known
                product_id=product.id,
                product_name=product.name,
                product_sku=product.sku or "",
                unit_price_cents=product.price_cents,
                vat_rate_bps=product.vat_rate_bps or 1900,
                quantity=quantity,
                line_total_cents=line_total,
            )
        )

    shipping = compute_shipping_cents(settings, subtotal)
    # Shipping assumed same default VAT as first item / 19%
    default_vat = resolved_lines[0][0].vat_rate_bps if resolved_lines else 1900
    vat_total += compute_vat_from_gross(shipping, default_vat or 1900)
    total = subtotal + shipping

    order = ShopOrder(
        id=str(uuid4()),
        order_number=generate_order_number(db),
        access_token=secrets.token_urlsafe(24),
        status="pending" if payment_method == "stripe" else "awaiting_payment",
        payment_method=payment_method,
        currency=(settings.shop_currency or "EUR").upper(),
        subtotal_cents=subtotal,
        shipping_cents=shipping,
        vat_cents=vat_total,
        total_cents=total,
        customer_email=email,
        customer_name=name,
        customer_phone=(customer.get("phone") or "").strip(),
        company=(customer.get("company") or "").strip(),
        address_line1=(customer.get("address_line1") or "").strip(),
        address_line2=(customer.get("address_line2") or "").strip(),
        postal_code=(customer.get("postal_code") or "").strip(),
        city=(customer.get("city") or "").strip(),
        country=((customer.get("country") or "DE").strip().upper())[:2],
        notes=(notes or "").strip(),
    )
    if not order.address_line1 or not order.postal_code or not order.city:
        raise HTTPException(status_code=400, detail="validation")

    db.add(order)
    db.flush()
    for item in order_items:
        item.order_id = order.id
        db.add(item)
    db.commit()
    db.refresh(order)

    checkout_url: Optional[str] = None
    if payment_method == "stripe":
        checkout_url = create_stripe_checkout_session(db, order, order_items, settings=settings)
    else:
        # Reserve stock for invoice orders immediately
        mark_inventory_reserved(db, order_items)
        db.commit()
        send_order_emails(db, order, order_items, settings=settings)

    return order, order_items, checkout_url


def mark_inventory_reserved(db: Session, items: list[ShopOrderItem]) -> None:
    for item in items:
        product = db.get(Product, item.product_id)
        if not product or not product.track_inventory:
            continue
        if product.stock_qty < item.quantity:
            raise HTTPException(status_code=409, detail="out_of_stock")
        product.stock_qty -= item.quantity


def create_stripe_checkout_session(
    db: Session,
    order: ShopOrder,
    items: list[ShopOrderItem],
    *,
    settings: Settings,
) -> str:
    origin = settings.shop_public_origin.rstrip("/")
    success = f"{origin}{settings.shop_success_path}?order={order.order_number}&token={order.access_token}&session_id={{CHECKOUT_SESSION_ID}}"
    cancel = f"{origin}{settings.shop_cancel_path}?cancelled=1"

    line_items = []
    for item in items:
        line_items.append(
            {
                "price_data": {
                    "currency": order.currency.lower(),
                    "unit_amount": item.unit_price_cents,
                    "product_data": {
                        "name": item.product_name,
                        "metadata": {"product_id": item.product_id, "sku": item.product_sku},
                    },
                },
                "quantity": item.quantity,
            }
        )
    if order.shipping_cents > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": order.currency.lower(),
                    "unit_amount": order.shipping_cents,
                    "product_data": {"name": "Versand / Shipping"},
                },
                "quantity": 1,
            }
        )

    data: list[tuple[str, str]] = [
        ("mode", "payment"),
        ("success_url", success),
        ("cancel_url", cancel),
        ("customer_email", order.customer_email),
        ("client_reference_id", order.id),
        ("metadata[order_id]", order.id),
        ("metadata[order_number]", order.order_number),
    ]
    for index, line in enumerate(line_items):
        prefix = f"line_items[{index}]"
        data.append((f"{prefix}[quantity]", str(line["quantity"])))
        price = line["price_data"]
        data.append((f"{prefix}[price_data][currency]", price["currency"]))
        data.append((f"{prefix}[price_data][unit_amount]", str(price["unit_amount"])))
        data.append((f"{prefix}[price_data][product_data][name]", price["product_data"]["name"]))
        metadata = price["product_data"].get("metadata") or {}
        for key, value in metadata.items():
            data.append((f"{prefix}[price_data][product_data][metadata][{key}]", str(value)))

    try:
        response = httpx.post(
            f"{STRIPE_API}/checkout/sessions",
            data=data,
            auth=(settings.shop_stripe_secret_key.strip(), ""),
            timeout=30.0,
        )
        if response.status_code >= 400:
            logger.error("Stripe checkout failed: %s", response.text)
            raise HTTPException(status_code=502, detail="stripe_failed")
        payload = response.json()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe checkout request error")
        raise HTTPException(status_code=502, detail="stripe_failed") from exc

    order.stripe_session_id = payload.get("id") or ""
    db.commit()
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=502, detail="stripe_failed")
    return url


def retrieve_stripe_session(session_id: str, settings: Settings) -> dict[str, Any]:
    response = httpx.get(
        f"{STRIPE_API}/checkout/sessions/{session_id}",
        auth=(settings.shop_stripe_secret_key.strip(), ""),
        timeout=20.0,
    )
    if response.status_code >= 400:
        logger.error("Stripe session retrieve failed: %s", response.text)
        raise HTTPException(status_code=502, detail="stripe_failed")
    return response.json()


def mark_order_paid(db: Session, order: ShopOrder, *, payment_intent: str = "", already_reserved: bool = False) -> ShopOrder:
    if order.status in {"paid", "fulfilled"}:
        return order
    items = get_order_items(db, order.id)
    if not already_reserved and order.payment_method == "stripe":
        mark_inventory_reserved(db, items)
    order.status = "paid"
    order.paid_at = _utc_now()
    if payment_intent:
        order.stripe_payment_intent = payment_intent
    db.commit()
    db.refresh(order)
    send_order_emails(db, order, items, settings=get_settings())
    return order


def confirm_stripe_order(db: Session, *, order_number: str, access_token: str, session_id: str) -> ShopOrder:
    order = get_order_by_number(db, order_number)
    if not order or order.access_token != access_token:
        raise HTTPException(status_code=404, detail="not_found")
    settings = get_settings()
    if not settings.shop_stripe_configured:
        raise HTTPException(status_code=400, detail="stripe_not_configured")
    session = retrieve_stripe_session(session_id, settings)
    if session.get("payment_status") != "paid" and session.get("status") != "complete":
        raise HTTPException(status_code=409, detail="payment_incomplete")
    if order.stripe_session_id and session.get("id") and order.stripe_session_id != session.get("id"):
        raise HTTPException(status_code=400, detail="validation")
    payment_intent = ""
    pi = session.get("payment_intent")
    if isinstance(pi, str):
        payment_intent = pi
    return mark_order_paid(db, order, payment_intent=payment_intent)


def send_order_emails(db: Session, order: ShopOrder, items: list[ShopOrderItem], *, settings: Settings) -> None:
    lines = [
        f"{item.quantity}× {item.product_name} — {item.line_total_cents / 100:.2f} {order.currency}"
        for item in items
    ]
    address = (
        f"{order.customer_name}\n"
        f"{order.company}\n".replace("\n\n", "\n")
        + f"{order.address_line1}\n"
        + (f"{order.address_line2}\n" if order.address_line2 else "")
        + f"{order.postal_code} {order.city}\n{order.country}"
    )
    status_label = {
        "paid": "bezahlt",
        "awaiting_payment": "warten auf Zahlung (Rechnung)",
        "pending": "ausstehend",
        "fulfilled": "versendet",
        "cancelled": "storniert",
    }.get(order.status, order.status)

    body = (
        f"Bestellung {order.order_number}\n"
        f"Status: {status_label}\n"
        f"Zahlung: {order.payment_method}\n\n"
        f"Positionen:\n" + "\n".join(lines) + "\n\n"
        f"Zwischensumme: {order.subtotal_cents / 100:.2f} {order.currency}\n"
        f"Versand: {order.shipping_cents / 100:.2f} {order.currency}\n"
        f"davon MwSt: {order.vat_cents / 100:.2f} {order.currency}\n"
        f"Gesamt: {order.total_cents / 100:.2f} {order.currency}\n\n"
        f"Lieferadresse:\n{address}\n\n"
        f"E-Mail: {order.customer_email}\n"
        f"Telefon: {order.customer_phone or '—'}\n"
    )
    if order.payment_method == "invoice" and settings.shop_bank_iban:
        body += (
            "\nZahlungsinformationen:\n"
            f"Empfänger: {settings.shop_bank_holder or settings.shop_brand_name}\n"
            f"IBAN: {settings.shop_bank_iban}\n"
            f"BIC: {settings.shop_bank_bic}\n"
            f"Bank: {settings.shop_bank_name}\n"
            f"Verwendungszweck: {order.order_number}\n"
        )

    send_plain_email(
        to_email=order.customer_email,
        subject=f"{settings.shop_brand_name} Bestellung {order.order_number}",
        body=f"Vielen Dank für Ihre Bestellung.\n\n{body}",
        settings=settings,
    )
    shop_inbox = settings.shop_contact
    if shop_inbox and shop_inbox.lower() != order.customer_email.lower():
        send_plain_email(
            to_email=shop_inbox,
            subject=f"Neue Shop-Bestellung {order.order_number}",
            body=body,
            settings=settings,
        )


def list_orders(db: Session, *, status: Optional[str] = None) -> list[ShopOrder]:
    stmt = select(ShopOrder).order_by(ShopOrder.created_at.desc())
    if status:
        stmt = stmt.where(ShopOrder.status == status)
    return list(db.scalars(stmt).all())


def update_order_status(db: Session, order: ShopOrder, status: str) -> ShopOrder:
    if status not in {"pending", "awaiting_payment", "paid", "fulfilled", "cancelled"}:
        raise HTTPException(status_code=400, detail="validation")
    order.status = status
    if status == "paid" and not order.paid_at:
        order.paid_at = _utc_now()
    if status == "fulfilled":
        order.fulfilled_at = _utc_now()
        if not order.paid_at:
            order.paid_at = order.fulfilled_at
    db.commit()
    db.refresh(order)
    return order
