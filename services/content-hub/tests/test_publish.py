def _publishable_article(client, it_auth_client, title: str, content: str) -> str:
    created = client.post("/api/articles", json={"title": title, "content": content})
    article_id = created.json()["article"]["id"]
    client.post(f"/api/workflow/articles/{article_id}/submit")
    it_auth_client.post(f"/api/workflow/articles/{article_id}/approve", json={})
    return article_id


def test_list_publish_channels(auth_client):
    response = auth_client.get("/api/publish/channels")
    assert response.status_code == 200
    channels = response.json()["channels"]
    assert len(channels) == 3
    assert {channel["channel"] for channel in channels} == {"teams", "outlook", "notion"}


def test_publish_article_in_mock_mode(auth_client, it_auth_client):
    article_id = _publishable_article(auth_client, it_auth_client, "Launch update", "<p>Hello teams</p>")

    response = auth_client.post(
        f"/api/publish/articles/{article_id}",
        json={"channels": ["teams", "notion", "outlook"]},
    )
    assert response.status_code == 200
    publication = response.json()["publication"]
    assert publication["resource_id"] == article_id
    assert len(publication["deliveries"]) == 3
    assert all(delivery["status"] == "sent" for delivery in publication["deliveries"])


def test_publish_history(auth_client, it_auth_client):
    article_id = _publishable_article(auth_client, it_auth_client, "History item", "<p>Track me</p>")
    auth_client.post(
        f"/api/publish/articles/{article_id}",
        json={"channels": ["teams"]},
    )

    history = auth_client.get("/api/publish/history")
    assert history.status_code == 200
    assert len(history.json()["publications"]) >= 1


def test_it_master_can_update_publish_settings(it_auth_client):
    response = it_auth_client.patch(
        "/api/publish/settings",
        json={
            "teams_enabled": True,
            "teams_team_id": "team-123",
            "teams_channel_id": "channel-456",
            "notion_enabled": True,
            "notion_database_id": "db-789",
        },
    )
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["teams_enabled"] is True
    assert settings["teams_team_id"] == "team-123"


def test_viewer_cannot_publish(client):
    from tests.conftest import _login, _seed_password_user

    _seed_password_user(role="editor")
    _login(client)
    created = client.post(
        "/api/articles",
        json={"title": "Blocked", "content": "x"},
    )
    article_id = created.json()["article"]["id"]

    _seed_password_user(role="viewer")
    _login(client)
    response = client.post(
        f"/api/publish/articles/{article_id}",
        json={"channels": ["teams"]},
    )
    assert response.status_code == 403
