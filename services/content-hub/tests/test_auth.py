from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def test_password_login_and_profile(client):
    from tests.conftest import _login, _seed_password_user

    _seed_password_user()
    response = _login(client)
    user = response.json()["user"]
    assert user["email"] == TEST_EMAIL
    assert user["name"] == "Demo User"
    assert user["role"] == "editor"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == TEST_EMAIL


def test_invalid_password_rejected(client):
    from tests.conftest import _seed_password_user

    _seed_password_user()
    response = client.post(
        "/api/auth/login",
        json={"email": TEST_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_initial_admin_bootstrap(client, monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@carbonauten.com")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "bootstrap-password")
    monkeypatch.setenv("INITIAL_ADMIN_NAME", "Admin User")
    monkeypatch.setenv("IT_ADMIN_EMAILS", "admin@carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app()) as bootstrap_client:
        login = bootstrap_client.post(
            "/api/auth/login",
            json={"email": "admin@carbonauten.com", "password": "bootstrap-password"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["role"] == "it_master"
    get_settings.cache_clear()


def test_language_preference_persists_in_session(auth_client):
    response = auth_client.patch("/api/user/language", json={"language": "zh-CN"})
    assert response.status_code == 200
    assert response.json()["user"]["language"] == "zh-CN"

    me = auth_client.get("/api/auth/me")
    assert me.json()["user"]["language"] == "zh-CN"


def test_unauthorized_without_session(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_logout_clears_session(auth_client):
    logout = auth_client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = auth_client.get("/api/auth/me")
    assert me.status_code == 401


def test_get_login_requires_microsoft_config(client):
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 400
    assert response.json()["code"] == "microsoft_auth_unavailable"
