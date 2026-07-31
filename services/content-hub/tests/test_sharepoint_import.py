from datetime import date, timedelta


def test_import_certificate_from_sharepoint_mock(auth_client):
    browse = auth_client.get("/api/files/browse", params={"source": "sharepoint", "item_id": "sp-zertifikate"})
    assert browse.status_code == 200
    files = browse.json()["files"]
    assert any(item["id"] == "sp-file-cert-iso9001" for item in files)

    response = auth_client.post(
        "/api/certificates/import-from-sharepoint",
        json={"item_id": "sp-file-cert-iso9001"},
    )
    assert response.status_code == 201
    payload = response.json()
    certificate = payload["certificate"]
    assert certificate["name"] == "ISO 9001 2024"
    assert certificate["category"] == "compliance"
    assert certificate["file_asset_id"]
    assert certificate["file_name"] == "ISO_9001_2024.pdf"
    assert "SharePoint" in certificate["notes"]
    assert payload["source"]["provider"] == "sharepoint"
    assert payload["source"]["mock"] is True
    assert certificate["valid_from"] == date.today().isoformat()
    assert certificate["valid_to"] == (date.today() + timedelta(days=365)).isoformat()

    listing = auth_client.get("/api/certificates")
    assert any(item["id"] == certificate["id"] for item in listing.json()["certificates"])


def test_import_ssl_certificate_guesses_category(auth_client):
    response = auth_client.post(
        "/api/certificates/import-from-sharepoint",
        json={
            "item_id": "sp-file-cert-ssl",
            "issuer": "Internal CA",
            "valid_from": date.today().isoformat(),
            "valid_to": (date.today() + timedelta(days=90)).isoformat(),
        },
    )
    assert response.status_code == 201
    certificate = response.json()["certificate"]
    assert certificate["category"] == "ssl"
    assert certificate["issuer"] == "Internal CA"
    assert certificate["valid_to"] == (date.today() + timedelta(days=90)).isoformat()


def test_import_sharepoint_file_as_asset(auth_client):
    response = auth_client.post(
        "/api/files/import-from-sharepoint",
        json={"item_id": "sp-file-cert-iso14001", "folder": "certificates"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["file"]["original_name"] == "ISO_14001_Umwelt.pdf"
    assert payload["file"]["size_bytes"] > 0
    assert payload["source"]["item_id"] == "sp-file-cert-iso14001"


def test_import_sharepoint_requires_editor(viewer_auth_client):
    response = viewer_auth_client.post(
        "/api/certificates/import-from-sharepoint",
        json={"item_id": "sp-file-cert-iso9001"},
    )
    assert response.status_code == 403


def test_import_sharepoint_unknown_item(auth_client):
    response = auth_client.post(
        "/api/certificates/import-from-sharepoint",
        json={"item_id": "missing-item"},
    )
    assert response.status_code == 404
