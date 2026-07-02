def test_dashboard_stats(auth_client):
    auth_client.post("/api/articles", json={"title": "Draft", "content": "x", "status": "draft"})
    auth_client.post("/api/articles", json={"title": "Live", "content": "y", "status": "published"})

    response = auth_client.get("/api/dashboard/stats")
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["drafts"] == 1
    assert stats["published"] == 1
    assert stats["files"] == 0
    assert stats["certificates"] == 0
