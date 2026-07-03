from datetime import date, timedelta


def test_dashboard_stats(auth_client, it_auth_client):
    draft = auth_client.post("/api/articles", json={"title": "Draft", "content": "x"})
    draft_id = draft.json()["article"]["id"]
    published = auth_client.post("/api/articles", json={"title": "Live", "content": "y"})
    pub_id = published.json()["article"]["id"]
    auth_client.post(f"/api/workflow/articles/{pub_id}/submit")
    it_auth_client.post(f"/api/workflow/articles/{pub_id}/approve", json={})
    auth_client.post(f"/api/workflow/articles/{draft_id}/submit")

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
    assert stats["drafts"] == 0
    assert stats["in_review"] == 1
    assert stats["published"] == 1
    assert stats["files"] == 0
    assert stats["certificates"] == 1
    assert stats["expiring_30"] == 1
    assert stats["expiring_60"] == 1
    assert stats["expiring_90"] == 1
