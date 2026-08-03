from io import BytesIO


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


def test_checkout_invoice_and_admin_orders(auth_client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    product = _create_published_product(auth_client)
    checkout = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 2}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer Name",
                "phone": "+491234",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
            "notes": "Bitte an Türklingel",
        },
    )
    assert checkout.status_code == 200
    payload = checkout.json()
    order = payload["order"]
    assert order["status"] == "awaiting_payment"
    assert order["payment_method"] == "invoice"
    assert order["total_cents"] == 9980
    assert order["access_token"]
    assert payload["checkout_url"] is None

    # stock decreased
    refreshed = auth_client.get(f"/api/products/{product['id']}").json()["product"]
    assert refreshed["stock_qty"] == 8

    public = auth_client.get(
        f"/api/shop/orders/{order['order_number']}",
        params={"token": order["access_token"]},
    )
    assert public.status_code == 200
    assert public.json()["order"]["customer_email"] == "buyer@example.com"

    admin = auth_client.get("/api/orders")
    assert admin.status_code == 200
    assert len(admin.json()["orders"]) == 1

    fulfilled = auth_client.patch(
        f"/api/orders/{order['id']}",
        json={"status": "fulfilled"},
    )
    assert fulfilled.status_code == 200
    assert fulfilled.json()["order"]["status"] == "fulfilled"
    get_settings.cache_clear()


def test_checkout_rejects_out_of_stock(auth_client):
    product = _create_published_product(auth_client, stock=1, track=True)
    response = auth_client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 5}],
            "customer": {
                "email": "buyer@example.com",
                "name": "Buyer",
                "address_line1": "Street 1",
                "postal_code": "10115",
                "city": "Berlin",
                "country": "DE",
            },
        },
    )
    assert response.status_code == 409


def test_product_stock_fields_roundtrip(auth_client):
    create = auth_client.post(
        "/api/products",
        json={
            "name": "Stocked Item",
            "price_cents": 1000,
            "is_published": True,
            "track_inventory": True,
            "stock_qty": 3,
        },
    )
    assert create.status_code == 201
    product = create.json()["product"]
    assert product["track_inventory"] is True
    assert product["stock_qty"] == 3
    public = auth_client.get(f"/api/shop/products/{product['slug']}")
    assert public.json()["product"]["in_stock"] is True
    assert public.json()["product"]["stock_available"] == 3


def test_shop_config_exposes_checkout_flags(client):
    response = client.get("/api/shop/config")
    assert response.status_code == 200
    payload = response.json()
    assert "stripe_enabled" in payload
    assert payload["invoice_enabled"] is True
    assert "legal" in payload
