from datetime import date, timedelta


def test_dashboard_stats(auth_client):
    auth_client.post("/api/articles", json={"title": "Draft", "content": "x", "status": "draft"})
    auth_client.post("/api/articles", json={"title": "Live", "content": "y", "status": "published"})
    auth_client.post(
        "/api/certificates",
        json={
            "name": "Soon",
            "category": "compliance",
            "issuer": "Auditor",
            "valid_from": date.today().isoformat(),
            "valid_to": (date.today() + timedelta(days=15)).isoformat(),
        },
    )
    response = auth_client.get("/api/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["drafts"] == 1
    assert stats["published"] == 1
    assert stats["files"] == 0
    assert stats["certificates"] == 1
    assert stats["expiring_30"] == 1
    assert stats["expiring_60"] == 1
    assert stats["expiring_90"] == 1
