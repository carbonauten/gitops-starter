def _create_published_product(auth_client, *, name="Invoice Pack", price=3000, stock=10, track=True):
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


def test_invoice_pdf_public_admin_and_customer(auth_client, client, monkeypatch):
    monkeypatch.setenv("SHOP_STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("SHOP_BANK_IBAN", "DE89370400440532013000")
    monkeypatch.setenv("SHOP_BANK_BIC", "COBADEFFXXX")
    monkeypatch.setenv("SHOP_BANK_NAME", "Commerzbank")
    monkeypatch.setenv("SHOP_BANK_HOLDER", "carbonauten GmbH")
    from app.config import get_settings

    get_settings.cache_clear()

    register = client.post(
        "/api/shop/auth/register",
        json={"email": "invoice@example.com", "name": "Invoice Buyer", "password": "password123"},
    )
    assert register.status_code == 200

    product = _create_published_product(auth_client)
    checkout = client.post(
        "/api/shop/checkout",
        json={
            "payment_method": "invoice",
            "items": [{"product_id": product["id"], "quantity": 1}],
            "customer": {
                "email": "ignored@example.com",
                "name": "Invoice Buyer",
                "address_line1": "Hauptstr. 1",
                "postal_code": "70173",
                "city": "Stuttgart",
                "country": "DE",
                "company": "Buyer GmbH",
            },
        },
    )
    assert checkout.status_code == 200
    order = checkout.json()["order"]
    assert order["access_token"]
    assert order["invoice_url"]
    assert order["order_number"] in order["invoice_url"]

    public = client.get(
        f"/api/shop/orders/{order['order_number']}/invoice.pdf",
        params={"token": order["access_token"]},
    )
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("application/pdf")
    assert public.content[:4] == b"%PDF"
    assert len(public.content) > 500
    assert f'filename="Rechnung-{order["order_number"]}.pdf"' in public.headers.get("content-disposition", "")

    bad = client.get(
        f"/api/shop/orders/{order['order_number']}/invoice.pdf",
        params={"token": "wrong-token"},
    )
    assert bad.status_code == 404

    admin = auth_client.get(f"/api/orders/{order['id']}/invoice.pdf")
    assert admin.status_code == 200
    assert admin.content[:4] == b"%PDF"

    mine = client.get(f"/api/shop/auth/me/orders/{order['id']}/invoice.pdf")
    assert mine.status_code == 200
    assert mine.content[:4] == b"%PDF"
    assert len(mine.content) > 500

    get_settings.cache_clear()


def test_build_invoice_pdf_contains_totals():
    from app.database import ShopOrder, ShopOrderItem
    from app.shop_invoice_service import build_invoice_pdf, invoice_number

    order = ShopOrder(
        id="o1",
        order_number="FC-20260807-0001",
        access_token="tok",
        status="awaiting_payment",
        payment_method="invoice",
        currency="EUR",
        subtotal_cents=3000,
        shipping_cents=0,
        vat_cents=479,
        total_cents=3000,
        customer_email="a@example.com",
        customer_name="Anna",
        address_line1="Street 1",
        postal_code="70173",
        city="Stuttgart",
        country="DE",
        company="ACME",
    )
    items = [
        ShopOrderItem(
            id="i1",
            order_id="o1",
            product_id="p1",
            product_name="Biochar",
            product_sku="BC-1",
            unit_price_cents=3000,
            vat_rate_bps=1900,
            quantity=1,
            line_total_cents=3000,
        )
    ]
    pdf = build_invoice_pdf(order, items)
    assert pdf.startswith(b"%PDF")
    assert invoice_number(order) == "RE-FC-20260807-0001"
