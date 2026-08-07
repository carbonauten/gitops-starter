from unittest.mock import patch


def _create_published_product(auth_client, *, name="Ship Pack", price=1990, stock=10, track=True):
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


def test_fulfill_order_with_tracking_and_email(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings
    from app.shop_order_service import build_tracking_url

    get_settings.cache_clear()

    assert "dhl.de" in build_tracking_url(carrier="dhl", tracking_number="JJD123", tracking_url="")
    assert build_tracking_url(carrier="other", tracking_number="X", tracking_url="https://track.example/X") == (
        "https://track.example/X"
    )

    product = _create_published_product(auth_client)
    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "shipme@example.com",
                "name": "Ship Me",
                "address_line1": "Street 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]

    paid = auth_client.patch(f"/api/orders/{order['id']}", json={"status": "paid"})
    assert paid.status_code == 200

    with patch("app.shop_order_service.send_plain_email", return_value=True) as send_email:
        shipped = auth_client.patch(
            f"/api/orders/{order['id']}",
            json={
                "status": "fulfilled",
                "shipping_carrier": "dhl",
                "tracking_number": "00340434161094015902",
                "tracking_url": "",
            },
        )
        assert shipped.status_code == 200
        body = shipped.json()["order"]
        assert body["status"] == "fulfilled"
        assert body["shipping_carrier"] == "dhl"
        assert body["tracking_number"] == "00340434161094015902"
        assert "dhl.de" in body["tracking_url"]
        assert body["fulfilled_at"]
        assert send_email.call_count >= 1
        subjects = [call.kwargs["subject"] for call in send_email.call_args_list]
        assert any("Versand" in subject for subject in subjects)

    fetched = auth_client.get(f"/api/orders/{order['id']}")
    assert fetched.json()["order"]["tracking_number"] == "00340434161094015902"
    get_settings.cache_clear()


def test_cancel_order_sends_status_email(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()
    product = _create_published_product(auth_client, name="Cancel Pack", stock=5)
    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "cancel@example.com",
                "name": "Cancel Me",
                "address_line1": "Street 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
        },
    )
    order = checkout.json()["order"]
    assert auth_client.get(f"/api/products/{product['id']}").json()["product"]["stock_qty"] == 4

    with patch("app.shop_order_service.send_plain_email", return_value=True) as send_email:
        cancelled = auth_client.patch(f"/api/orders/{order['id']}", json={"status": "cancelled"})
        assert cancelled.status_code == 200
        assert cancelled.json()["order"]["status"] == "cancelled"
        assert send_email.call_count >= 1
        subjects = [call.kwargs["subject"] for call in send_email.call_args_list]
        assert any("Storno" in subject for subject in subjects)

    assert auth_client.get(f"/api/products/{product['id']}").json()["product"]["stock_qty"] == 5
    get_settings.cache_clear()
