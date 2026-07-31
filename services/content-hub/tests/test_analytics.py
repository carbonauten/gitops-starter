from datetime import date, timedelta


def test_analytics_overview_requires_auth(client):
    response = client.get("/api/analytics/overview")
    assert response.status_code == 401


def test_analytics_overview_empty(auth_client):
    response = auth_client.get("/api/analytics/overview?days=30")
    assert response.status_code == 200
    overview = response.json()["overview"]
    assert overview["range_days"] == 30
    assert overview["articles"]["total"] == 0
    assert overview["certificates"]["total"] == 0
    assert overview["publications"]["total"] == 0
    assert overview["files"]["total"] == 0
    assert len(overview["publications"]["by_day"]) == 30


def test_analytics_overview_with_content(auth_client, it_auth_client):
    draft = auth_client.post("/api/articles", json={"title": "Draft A", "content": "x"}).json()["article"]
    live = auth_client.post("/api/articles", json={"title": "Live B", "content": "y"}).json()["article"]
    auth_client.post(f"/api/workflow/articles/{live['id']}/submit")
    it_auth_client.post(f"/api/workflow/articles/{live['id']}/approve", json={})

    auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO Soon",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": date.today().isoformat(),
            "valid_to": (date.today() + timedelta(days=20)).isoformat(),
        },
    )
    auth_client.post(
        "/api/certificates",
        json={
            "name": "Old Cert",
            "category": "product",
            "issuer": "Lab",
            "valid_from": (date.today() - timedelta(days=400)).isoformat(),
            "valid_to": (date.today() - timedelta(days=10)).isoformat(),
        },
    )

    published = auth_client.post(
        f"/api/publish/articles/{live['id']}",
        json={"channels": ["teams", "notion"]},
    )
    assert published.status_code == 200

    response = auth_client.get("/api/analytics/overview?days=90")
    assert response.status_code == 200
    overview = response.json()["overview"]

    assert overview["articles"]["total"] == 2
    assert overview["articles"]["by_status"].get("draft") == 1
    assert overview["articles"]["by_status"].get("published") == 1
    assert overview["certificates"]["total"] == 2
    assert overview["certificates"]["by_status"].get("expiring") == 1
    assert overview["certificates"]["by_status"].get("expired") == 1
    assert overview["certificates"]["by_category"].get("compliance") == 1
    assert overview["certificates"]["by_category"].get("product") == 1
    assert overview["certificates"]["expiring_30"] == 1
    assert overview["publications"]["total"] == 1
    assert overview["publications"]["in_range"] == 1
    assert overview["publications"]["deliveries"]["total"] == 2
    assert any(item["channel"] == "teams" for item in overview["publications"]["deliveries"]["by_channel"])
    assert len(overview["publications"]["recent"]) == 1
    assert overview["activity"]["top_authors"]
    assert overview["activity"]["top_authors"][0]["article_count"] >= 1
    assert draft["id"]
