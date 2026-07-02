from datetime import date, timedelta
from io import BytesIO


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def test_create_list_update_and_search_certificate(auth_client):
    create = auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO 9001",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": _past(365),
            "valid_to": _future(20),
            "responsible_name": "Quality Team",
            "responsible_email": "quality@example.com",
            "notes": "Annual audit",
        },
    )
    assert create.status_code == 201
    certificate = create.json()["certificate"]
    assert certificate["status"] == "expiring"
    certificate_id = certificate["id"]

    listing = auth_client.get("/api/certificates")
    assert listing.status_code == 200
    assert len(listing.json()["certificates"]) == 1

    update = auth_client.patch(
        f"/api/certificates/{certificate_id}",
        json={"renewal_in_progress": True},
    )
    assert update.status_code == 200
    assert update.json()["certificate"]["status"] == "renewal"

    search = auth_client.get("/api/search", params={"q": "ISO"})
    assert search.status_code == 200
    assert any(item["type"] == "certificate" for item in search.json()["results"])


def test_certificate_status_filters_and_export(auth_client):
    auth_client.post(
        "/api/certificates",
        json={
            "name": "Expired SSL",
            "category": "ssl",
            "issuer": "Let's Encrypt",
            "valid_from": _past(400),
            "valid_to": _past(10),
        },
    )
    auth_client.post(
        "/api/certificates",
        json={
            "name": "Valid Product Cert",
            "category": "product",
            "issuer": "CE Body",
            "valid_from": _past(30),
            "valid_to": _future(200),
        },
    )

    expired = auth_client.get("/api/certificates", params={"status": "expired"})
    assert expired.status_code == 200
    assert len(expired.json()["certificates"]) == 1

    export = auth_client.get("/api/certificates/export")
    assert export.status_code == 200
    assert "Expired SSL" in export.text
    assert "Valid Product Cert" in export.text


def test_certificate_with_file_attachment(auth_client):
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("cert.pdf", BytesIO(b"%PDF-1.4 test"), "application/pdf")},
        data={"folder": "certificates"},
    )
    assert upload.status_code == 201
    file_id = upload.json()["file"]["id"]

    create = auth_client.post(
        "/api/certificates",
        json={
            "name": "REACH Declaration",
            "category": "product",
            "issuer": "Internal Lab",
            "valid_from": _past(10),
            "valid_to": _future(300),
            "file_asset_id": file_id,
        },
    )
    assert create.status_code == 201
    assert create.json()["certificate"]["file_name"] == "cert.pdf"


def test_delete_certificate(auth_client):
    create = auth_client.post(
        "/api/certificates",
        json={
            "name": "Temp Cert",
            "category": "training",
            "issuer": "HR",
            "valid_from": _past(1),
            "valid_to": _future(30),
        },
    )
    certificate_id = create.json()["certificate"]["id"]
    delete = auth_client.delete(f"/api/certificates/{certificate_id}")
    assert delete.status_code == 204
    assert auth_client.get(f"/api/certificates/{certificate_id}").status_code == 404
