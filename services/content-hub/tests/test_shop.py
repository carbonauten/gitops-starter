from datetime import date
from io import BytesIO


def test_shop_config_public(client):
    response = client.get("/api/shop/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["brand_name"] == "FuckCo2"
    assert "fuckco2.shop" in payload["hosts"]


def test_product_crud_and_public_shop(auth_client):
    empty = auth_client.get("/api/shop/products")
    assert empty.status_code == 200
    assert empty.json()["products"] == []

    create = auth_client.post(
        "/api/products",
        json={
            "name": "Biochar Sample Pack",
            "short_description": "1 kg sample",
            "description": "Premium biochar for garden use.",
            "price_cents": 2490,
            "currency": "EUR",
            "sku": "BC-1KG",
            "is_published": False,
        },
    )
    assert create.status_code == 201
    product = create.json()["product"]
    assert product["slug"] == "biochar-sample-pack"
    assert product["is_published"] is False
    product_id = product["id"]

    # unpublished not visible in public shop
    public = auth_client.get("/api/shop/products")
    assert public.json()["products"] == []

    publish = auth_client.patch(
        f"/api/products/{product_id}",
        json={"is_published": True},
    )
    assert publish.status_code == 200
    assert publish.json()["product"]["is_published"] is True

    listing = auth_client.get("/api/shop/products")
    assert len(listing.json()["products"]) == 1
    assert listing.json()["products"][0]["name"] == "Biochar Sample Pack"

    detail = auth_client.get("/api/shop/products/biochar-sample-pack")
    assert detail.status_code == 200
    assert detail.json()["product"]["price_cents"] == 2490

    admin_list = auth_client.get("/api/products")
    assert len(admin_list.json()["products"]) == 1


def test_product_with_image_public(auth_client):
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("biochar.png", BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png")},
        data={"folder": "products"},
    )
    assert upload.status_code == 201
    file_id = upload.json()["file"]["id"]

    create = auth_client.post(
        "/api/products",
        json={
            "name": "Biochar Bag 10kg",
            "price_cents": 8900,
            "is_published": True,
            "image_file_asset_id": file_id,
        },
    )
    assert create.status_code == 201
    product = create.json()["product"]
    assert product["image_url"] == f"/api/shop/products/{product['slug']}/image"

    image = auth_client.get(product["image_url"])
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")


def test_product_requires_editor(viewer_auth_client):
    response = viewer_auth_client.post(
        "/api/products",
        json={"name": "Nope", "price_cents": 100, "is_published": True},
    )
    assert response.status_code == 403


def test_dashboard_includes_product_counts(auth_client):
    auth_client.post(
        "/api/products",
        json={"name": "Published Item", "price_cents": 1000, "is_published": True},
    )
    auth_client.post(
        "/api/products",
        json={"name": "Draft Item", "price_cents": 500, "is_published": False},
    )
    stats = auth_client.get("/api/dashboard/stats").json()["stats"]
    assert stats["products"] == 2
    assert stats["products_published"] == 1
