from urllib.parse import parse_qs, urlparse

import pytest

from tests.conftest import TEST_PASSWORD, _seed_password_user


def test_effective_redirect_uri_uses_app_public_url(monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://app.carbonauten.com")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    assert settings.effective_redirect_uri == "https://app.carbonauten.com/api/auth/callback"
    assert settings.cookie_secure is True
    get_settings.cache_clear()


def test_entra_login_redirects_to_microsoft(client, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://app.carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "login.microsoftonline.com/tenant-id" in location
    assert "redirect_uri=https%3A%2F%2Fapp.carbonauten.com%2Fapi%2Fapi%2Fauth%2Fcallback" not in location
    assert "redirect_uri=https%3A%2F%2Fapp.carbonauten.com%2Fapi%2Fauth%2Fcallback" in location
    get_settings.cache_clear()


def test_sso_links_existing_password_user():
    from app.database import _SessionLocal
    from app.user_service import get_user_by_email, upsert_user_from_login

    _seed_password_user(email="mike.mueller@carbonauten.com")
    db = _SessionLocal()
    try:
        user = upsert_user_from_login(
            db,
            entra_id="entra-object-id-123",
            email="mike.mueller@carbonauten.com",
            name="Mike Mueller",
            language="de",
        )
        assert user.entra_id == "entra-object-id-123"
        linked = get_user_by_email(db, "mike.mueller@carbonauten.com")
        assert linked is not None
        assert linked.id == user.id
        assert linked.password_hash
    finally:
        db.close()


def test_entra_callback_creates_session(client, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://app.carbonauten.com")
    from app.config import get_settings

    get_settings.cache_clear()

    async def fake_exchange(code: str):
        return {
            "id": "entra-object-id-999",
            "name": "Mike Mueller",
            "email": "mike.mueller@carbonauten.com",
            "language": "de",
        }

    monkeypatch.setattr("app.routes.auth.exchange_code_for_user", fake_exchange)

    login_response = client.get("/api/auth/login?lang=de", follow_redirects=False)
    assert login_response.status_code == 302
    state = parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]

    callback = client.get(
        f"/api/auth/callback?code=test-code&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert callback.headers["location"] == "/"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    user = me.json()["user"]
    assert user["email"] == "mike.mueller@carbonauten.com"
    assert user["name"] == "Mike Mueller"
    assert user["language"] == "de"

    password_login = client.post(
        "/api/auth/login",
        json={"email": "mike.mueller@carbonauten.com", "password": TEST_PASSWORD},
    )
    assert password_login.status_code == 401
    get_settings.cache_clear()
