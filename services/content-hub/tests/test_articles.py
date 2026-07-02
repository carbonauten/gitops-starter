def test_create_list_and_update_article(auth_client):
    create = auth_client.post(
        "/api/articles",
        json={"title": "Weekly update", "content": "<p>Hello team</p>", "status": "draft"},
    )
    assert create.status_code == 201
    article_id = create.json()["article"]["id"]

    listing = auth_client.get("/api/articles")
    assert listing.status_code == 200
    assert len(listing.json()["articles"]) == 1

    update = auth_client.patch(
        f"/api/articles/{article_id}",
        json={"status": "published", "title": "Weekly update published"},
    )
    assert update.status_code == 200
    assert update.json()["article"]["status"] == "published"

    search = auth_client.get("/api/search", params={"q": "Weekly"})
    assert search.status_code == 200
    assert any(item["type"] == "article" for item in search.json()["results"])


def test_article_templates(auth_client):
    response = auth_client.get("/api/articles/templates")
    assert response.status_code == 200
    templates = response.json()["templates"]
    assert len(templates) == 3
    assert any(item["id"] == "weekly_report" for item in templates)


def test_delete_article(auth_client):
    create = auth_client.post("/api/articles", json={"title": "Temp", "content": "", "status": "draft"})
    article_id = create.json()["article"]["id"]
    delete = auth_client.delete(f"/api/articles/{article_id}")
    assert delete.status_code == 204
    assert auth_client.get(f"/api/articles/{article_id}").status_code == 404
