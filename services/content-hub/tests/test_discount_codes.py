from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch


def _create_published_product(auth_client, *, name="Biochar 5kg", price=4990, stock=10, track=True):
    create = auth_client.post(
        "/api/products",
        json={
            "name": name,
            "price_cents": price,
            "is_published": True,
            "track_inventory": track,
            "stock_qty": stock,
            "vat_rate_bps": 1900,
        },
    )
    assert create.status_code == 201
    return create.json()["product"]


def _create_percent_code(auth_client, *, code="SAVE10", percent_off_bps=1000, **extra):
    payload = {
        "code": code,
        "discount_type": "percent",
        "percent_off_bps": percent_off_bps,
        **extra,
    }
    response = auth_client.post("/api/discount-codes", json=payload)
    assert response.status_code == 201
    return response.json()["discount_code"]


def test_viewer_cannot_create_discount_codes(viewer_auth_client):
    # viewer has read-only shop access (require_shop_access) but is not in
    # EDIT_ROLES, so the mutating require_shop_editor-gated endpoint must
    # reject it even though listing (require_shop_access) would not.
    response = viewer_auth_client.post(
        "/api/discount-codes",
        json={"code": "NOPE", "discount_type": "percent", "percent_off_bps": 500},
    )
    assert response.status_code == 403


def test_admin_creates_lists_and_deletes_discount_code(auth_client):
    code = _create_percent_code(auth_client)
    assert code["code"] == "SAVE10"
    assert code["discount_type"] == "percent"
    assert code["percent_off_bps"] == 1000
    assert code["redemption_count"] == 0

    listing = auth_client.get("/api/discount-codes")
    assert listing.status_code == 200
    assert any(c["id"] == code["id"] for c in listing.json()["discount_codes"])

    deleted = auth_client.delete(f"/api/discount-codes/{code['id']}")
    assert deleted.status_code == 204

    listing_after = auth_client.get("/api/discount-codes")
    assert not any(c["id"] == code["id"] for c in listing_after.json()["discount_codes"])


def test_create_discount_code_rejects_duplicate(auth_client):
    _create_percent_code(auth_client, code="DUPE")
    response = auth_client.post(
        "/api/discount-codes",
        json={"code": "dupe", "discount_type": "percent", "percent_off_bps": 500},
    )
    assert response.status_code == 409


def test_checkout_applies_percent_discount(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    _create_percent_code(auth_client, code="SAVE10", percent_off_bps=1000)
    product = _create_published_product(auth_client, price=10000)

    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "save10",
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    assert order["discount_code"] == "SAVE10"
    assert order["discount_cents"] == 1000  # 10% of 10000
    assert order["subtotal_cents"] == 10000
    assert order["total_cents"] == 9000 + order["shipping_cents"]

    codes = auth_client.get("/api/discount-codes").json()["discount_codes"]
    assert next(c for c in codes if c["code"] == "SAVE10")["redemption_count"] == 1


def test_checkout_applies_fixed_discount_capped_at_subtotal(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    auth_client.post(
        "/api/discount-codes",
        json={"code": "BIGFIXED", "discount_type": "fixed", "amount_off_cents": 999999},
    )
    product = _create_published_product(auth_client, name="Cheap item", price=500)

    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "BIGFIXED",
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    # Discount never exceeds the subtotal itself - a fixed-amount code
    # bigger than the cart must not produce a negative subtotal.
    assert order["discount_cents"] == 500
    assert order["subtotal_cents"] == 500


def test_checkout_rejects_invalid_discount_code(auth_client):
    product = _create_published_product(auth_client)
    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "NOPE",
        },
    )
    assert checkout.status_code == 404
    assert checkout.json()["code"] == "discount_code_invalid"


def test_checkout_rejects_expired_discount_code(auth_client):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    _create_percent_code(auth_client, code="OLD", valid_until=past)
    product = _create_published_product(auth_client)

    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "OLD",
        },
    )
    assert checkout.status_code == 400
    assert checkout.json()["code"] == "discount_code_expired"


def test_checkout_rejects_discount_code_below_minimum_order(auth_client):
    _create_percent_code(auth_client, code="MIN50", min_order_cents=5000)
    product = _create_published_product(auth_client, price=1000)

    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "MIN50",
        },
    )
    assert checkout.status_code == 400
    assert checkout.json()["code"] == "discount_code_minimum_not_met"


def test_checkout_rejects_discount_code_at_redemption_limit(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    _create_percent_code(auth_client, code="ONEUSE", max_redemptions=1)
    product = _create_published_product(auth_client, stock=10)

    customer = {
        "email": "buyer@example.com",
        "name": "Buyer",
        "address_line1": "Hauptstr. 1",
        "postal_code": "70173",
        "city": "Stuttgart",
        "country": "DE",
    }
    first = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": customer,
            "discount_code": "ONEUSE",
        },
    )
    assert first.status_code == 200

    second = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": customer,
            "discount_code": "ONEUSE",
        },
    )
    assert second.status_code == 400
    assert second.json()["code"] == "discount_code_limit_reached"


def test_cancelling_order_releases_discount_redemption(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    code = _create_percent_code(auth_client, code="RELEASE", max_redemptions=1)
    product = _create_published_product(auth_client, stock=10)

    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "RELEASE",
        },
    )
    assert checkout.status_code == 200
    order_id = checkout.json()["order"]["id"]

    codes_after_order = auth_client.get("/api/discount-codes").json()["discount_codes"]
    assert next(c for c in codes_after_order if c["id"] == code["id"])["redemption_count"] == 1

    cancelled = auth_client.patch(f"/api/orders/{order_id}", json={"status": "cancelled"})
    assert cancelled.status_code == 200

    codes_after_cancel = auth_client.get("/api/discount-codes").json()["discount_codes"]
    assert next(c for c in codes_after_cancel if c["id"] == code["id"])["redemption_count"] == 0

    # The redemption slot is free again, so the same code can be reused.
    retry = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "buyer2@example.com",
                "name": "Buyer Two",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "discount_code": "RELEASE",
        },
    )
    assert retry.status_code == 200


def test_apply_discount_preview_does_not_reserve_redemption(auth_client):
    _create_percent_code(auth_client, code="PREVIEW10", percent_off_bps=1000, max_redemptions=1)

    preview = auth_client.post(
        "/api/shop/apply-discount",
        json={"code": "preview10", "subtotal_cents": 5000},
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["code"] == "PREVIEW10"
    assert payload["discount_cents"] == 500

    codes = auth_client.get("/api/discount-codes").json()["discount_codes"]
    assert next(c for c in codes if c["code"] == "PREVIEW10")["redemption_count"] == 0


def test_stripe_checkout_line_items_reflect_discount(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    _create_percent_code(auth_client, code="STRIPE20", percent_off_bps=2000)
    product = _create_published_product(auth_client, name="Stripe item", price=10000, stock=5)

    captured: dict = {}

    def fake_post(url, data=None, **kwargs):
        captured["data"] = data

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"id": "cs_test_123", "url": "https://stripe.test/session"}

        return FakeResponse()

    with patch("app.shop_order_service.httpx.post", side_effect=fake_post):
        checkout = auth_client.post(
            "/api/shop/checkout",
            json={
                "payment_method": "stripe",
                "items": [{"product_id": product["id"], "quantity": 1}],
                "customer": {
                    "email": "buyer@example.com",
                    "name": "Buyer",
                    "address_line1": "Hauptstr. 1",
                    "postal_code": "70173",
                    "city": "Stuttgart",
                    "country": "DE",
                },
                "discount_code": "STRIPE20",
            },
        )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    assert order["discount_cents"] == 2000

    # Sum every line_items[n][price_data][unit_amount] * quantity sent to
    # Stripe and confirm it matches order.total_cents exactly - a mismatch
    # here would mean the customer is charged a different amount at Stripe
    # than the order record says.
    data = dict(captured["data"])
    total_sent = 0
    index = 0
    while f"line_items[{index}][price_data][unit_amount]" in data:
        amount = int(data[f"line_items[{index}][price_data][unit_amount]"])
        quantity = int(data[f"line_items[{index}][quantity]"])
        total_sent += amount * quantity
        index += 1
    assert total_sent == order["total_cents"]
