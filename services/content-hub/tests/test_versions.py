def test_article_update_creates_revision(auth_client):
    created = auth_client.post("/api/articles", json={"title": "Versioned", "content": "<p>v1</p>"})
    article_id = created.json()["article"]["id"]

    auth_client.patch(
        f"/api/articles/{article_id}",
        json={"title": "Versioned v2", "content": "<p>v2</p>"},
    )

    versions = auth_client.get(f"/api/versions/article/{article_id}")
    assert versions.status_code == 200
    items = versions.json()["versions"]
    assert len(items) == 1
    assert items[0]["version_number"] == 1
    assert items[0]["changed_by_name"]


def test_compare_article_version_with_current(auth_client):
    created = auth_client.post("/api/articles", json={"title": "Compare me", "content": "<p>old</p>"})
    article_id = created.json()["article"]["id"]
    auth_client.patch(f"/api/articles/{article_id}", json={"content": "<p>new</p>"})

    compare = auth_client.get(f"/api/versions/article/{article_id}/compare?from_version=1")
    assert compare.status_code == 200
    payload = compare.json()
    assert payload["to_version"] == "current"
    fields = {change["field"] for change in payload["changes"]}
    assert "content" in fields


def test_certificate_update_creates_revision(auth_client):
    created = auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO 9001",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-01-01",
            "responsible_name": "QA",
            "responsible_email": "qa@example.com",
        },
    )
    certificate_id = created.json()["certificate"]["id"]
    auth_client.patch(f"/api/certificates/{certificate_id}", json={"notes": "Updated notes"})

    versions = auth_client.get(f"/api/versions/certificate/{certificate_id}")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) == 1
