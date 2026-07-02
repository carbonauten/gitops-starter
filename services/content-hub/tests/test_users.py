def test_mock_login_creates_user_with_editor_role(auth_client):
    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    user = me.json()["user"]
    assert user["email"] == "demo@example.com"
    assert user["role"] == "editor"
    assert user["db_id"]


def test_it_admin_email_gets_master_role(client, monkeypatch):
    monkeypatch.setenv("IT_ADMIN_EMAILS", "demo@example.com")
    from app.config import get_settings

    get_settings.cache_clear()
    client.get("/api/auth/login", follow_redirects=False)
    me = client.get("/api/auth/me")
    assert me.json()["user"]["role"] == "it_master"
    get_settings.cache_clear()


def test_it_master_can_manage_users(it_auth_client):
    listing = it_auth_client.get("/api/user/users")
    assert listing.status_code == 200
    users = listing.json()["users"]
    assert len(users) >= 1
    assert any(user["role"] == "it_master" for user in users)


def test_it_admin_email_promoted_on_me_without_relogin(client, monkeypatch):
    client.get("/api/auth/login", follow_redirects=False)
    me = client.get("/api/auth/me")
    assert me.json()["user"]["role"] == "editor"

    monkeypatch.setenv("IT_ADMIN_EMAILS", "demo@example.com")
    from app.config import get_settings

    get_settings.cache_clear()
    me = client.get("/api/auth/me")
    assert me.json()["user"]["role"] == "it_master"
    get_settings.cache_clear()


def test_editor_cannot_manage_users(auth_client):
    response = auth_client.get("/api/user/users")
    assert response.status_code == 403


def test_viewer_cannot_create_articles(viewer_auth_client):
    response = viewer_auth_client.post("/api/articles", json={"title": "Blocked", "content": "x", "status": "draft"})
    assert response.status_code == 403
