from datetime import datetime, timedelta, timezone


def _create_published_product(auth_client, *, name="Biochar Return", price=2500, stock=10, track=True):
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


def test_shop_return_request_complete_restores_stock_and_credits(auth_client, client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("SHOP_CO2_CREDITS_PER_EURO", "1")
    monkeypatch.setenv("SHOP_RETURN_WINDOW_DAYS", "30")
    from app.config import get_settings

    get_settings.cache_clear()

    register = client.post(
        "/api/shop/auth/register",
        json={"email": "returner@example.com", "name": "Returner", "password": "password123"},
    )
    assert register.status_code == 200

    product = _create_published_product(auth_client, stock=5, track=True)
    checkout = client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 2}],
            "customer": {
                "email": "ignored@example.com",
                "name": "Returner",
                "address_line1": "Street 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    assert auth_client.get(f"/api/products/{product['id']}").json()["product"]["stock_qty"] == 3

    paid = auth_client.patch(f"/api/orders/{order['id']}", json={"status": "paid"})
    assert paid.status_code == 200
    assert paid.json()["order"]["credits_earned"] == 50
    assert client.get("/api/shop/auth/me/credits").json()["balance"] == 50

    requested = client.post(
        f"/api/shop/auth/me/orders/{order['id']}/returns",
        json={"reason": "damaged", "customer_note": "Box kaputt"},
    )
    assert requested.status_code == 201
    ret = requested.json()["return"]
    assert ret["status"] == "requested"
    assert ret["reason"] == "damaged"

    mine = client.get("/api/shop/auth/me/returns")
    assert mine.status_code == 200
    assert len(mine.json()["returns"]) == 1

    admin_list = auth_client.get("/api/shop-returns", params={"status": "requested"})
    assert admin_list.status_code == 200
    assert len(admin_list.json()["returns"]) == 1

    completed = auth_client.patch(
        f"/api/shop-returns/{ret['id']}",
        json={"status": "completed", "admin_note": "Ware zurück, Gutschrift manuell"},
    )
    assert completed.status_code == 200
    done = completed.json()["return"]
    assert done["status"] == "completed"
    assert done["inventory_restored"] is True
    assert done["credits_reversed"] == 50

    assert auth_client.get(f"/api/products/{product['id']}").json()["product"]["stock_qty"] == 5
    assert client.get("/api/shop/auth/me/credits").json()["balance"] == 0
    assert auth_client.get(f"/api/orders/{order['id']}").json()["order"]["status"] == "returned"

    duplicate = client.post(
        f"/api/shop/auth/me/orders/{order['id']}/returns",
        json={"reason": "other"},
    )
    assert duplicate.status_code == 409
    get_settings.cache_clear()


def test_shop_return_window_and_status_guards(auth_client, client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("SHOP_RETURN_WINDOW_DAYS", "30")
    from app.config import get_settings
    from app.database import ShopOrder, _SessionLocal

    get_settings.cache_clear()

    client.post(
        "/api/shop/auth/register",
        json={"email": "window@example.com", "name": "Window", "password": "password123"},
    )
    product = _create_published_product(auth_client, stock=4, track=True)
    checkout = client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "window@example.com",
                "name": "Window",
                "address_line1": "Street 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
        },
    )
    order = checkout.json()["order"]

    too_early = client.post(
        f"/api/shop/auth/me/orders/{order['id']}/returns",
        json={"reason": "changed_mind"},
    )
    assert too_early.status_code == 400

    auth_client.patch(f"/api/orders/{order['id']}", json={"status": "paid"})

    db = _SessionLocal()
    try:
        row = db.get(ShopOrder, order["id"])
        assert row is not None
        row.paid_at = datetime.now(timezone.utc) - timedelta(days=45)
        db.commit()
    finally:
        db.close()

    expired = client.post(
        f"/api/shop/auth/me/orders/{order['id']}/returns",
        json={"reason": "changed_mind"},
    )
    assert expired.status_code == 400

    db = _SessionLocal()
    try:
        row = db.get(ShopOrder, order["id"])
        assert row is not None
        row.paid_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    ok = client.post(
        f"/api/shop/auth/me/orders/{order['id']}/returns",
        json={"reason": "changed_mind"},
    )
    assert ok.status_code == 201
    ret_id = ok.json()["return"]["id"]

    rejected = auth_client.patch(
        f"/api/shop-returns/{ret_id}",
        json={"status": "rejected", "admin_note": "Nein"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["return"]["status"] == "rejected"
    assert auth_client.get(f"/api/products/{product['id']}").json()["product"]["stock_qty"] == 3
    get_settings.cache_clear()
