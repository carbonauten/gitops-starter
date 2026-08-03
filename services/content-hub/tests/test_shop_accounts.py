def test_shop_customer_register_login_and_credits(auth_client, client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("SHOP_CO2_CREDITS_PER_EURO", "1")
    from app.config import get_settings

    get_settings.cache_clear()

    register = client.post(
        "/api/shop/auth/register",
        json={"email": "shopper@example.com", "name": "Shopper", "password": "password123"},
    )
    assert register.status_code == 200
    customer = register.json()["customer"]
    assert customer["email"] == "shopper@example.com"
    assert customer["co2_credit_balance"] == 0

    me = client.get("/api/shop/auth/me")
    assert me.status_code == 200
    assert me.json()["customer"]["id"] == customer["id"]

    product = auth_client.post(
        "/api/products",
        json={
            "name": "Credit Pack",
            "price_cents": 2500,
            "is_published": True,
            "track_inventory": False,
            "stock_qty": 0,
        },
    ).json()["product"]

    checkout = client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 2}],
            "customer": {
                "email": "ignored@example.com",
                "name": "Shopper",
                "address_line1": "Street 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
            },
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    assert order["customer_id"] == customer["id"]
    assert order["customer_email"] == "shopper@example.com"
    assert order["credits_earned"] == 0

    paid = auth_client.patch(f"/api/orders/{order['id']}", json={"status": "paid"})
    assert paid.status_code == 200
    assert paid.json()["order"]["credits_earned"] == 50  # 50 EUR * 1

    credits = client.get("/api/shop/auth/me/credits")
    assert credits.status_code == 200
    assert credits.json()["balance"] == 50
    assert len(credits.json()["ledger"]) == 1

    # idempotent second mark paid
    paid_again = auth_client.patch(f"/api/orders/{order['id']}", json={"status": "paid"})
    assert paid_again.json()["order"]["credits_earned"] == 50
    assert client.get("/api/shop/auth/me/credits").json()["balance"] == 50

    admin = auth_client.get("/api/shop-customers")
    assert admin.status_code == 200
    assert any(item["email"] == "shopper@example.com" for item in admin.json()["customers"])
    get_settings.cache_clear()


def test_shop_access_flag_hides_product_api(client, monkeypatch):
    monkeypatch.setenv("IT_ADMIN_EMAILS", "")
    from app.config import get_settings
    from app.database import UserAccount, _SessionLocal
    from app.password_service import hash_password
    from sqlalchemy import select

    get_settings.cache_clear()

    with client:
        # bootstrap DB via first request
        client.get("/api/health")
        db = _SessionLocal()
        try:
            user = db.scalar(select(UserAccount).where(UserAccount.email == "editor-nosshop@example.com"))
            if user is None:
                user = UserAccount(
                    entra_id="editor-no-shop",
                    email="editor-nosshop@example.com",
                    name="No Shop",
                    role="editor",
                    password_hash=hash_password("password123"),
                    is_active=True,
                    can_manage_shop=False,
                )
                db.add(user)
            else:
                user.can_manage_shop = False
                user.role = "editor"
            db.commit()
        finally:
            db.close()

        login = client.post(
            "/api/auth/login",
            json={"email": "editor-nosshop@example.com", "password": "password123"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["can_manage_shop"] is False

        blocked = client.get("/api/products")
        assert blocked.status_code == 403

        blocked_orders = client.get("/api/orders")
        assert blocked_orders.status_code == 403
    get_settings.cache_clear()


def test_employee_shop_access_toggle(it_auth_client):
    created = it_auth_client.post(
        "/api/user/users",
        json={
            "email": "shop-editor@example.com",
            "name": "Shop Editor",
            "password": "password123",
            "role": "editor",
            "can_manage_shop": False,
        },
    )
    assert created.status_code == 200
    user = created.json()["user"]
    assert user["can_manage_shop"] is False

    enabled = it_auth_client.patch(
        f"/api/user/users/{user['db_id']}/shop-access",
        json={"can_manage_shop": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["user"]["can_manage_shop"] is True
