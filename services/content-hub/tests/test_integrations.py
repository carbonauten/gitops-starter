from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select


def test_integration_status_forbidden_for_viewer(viewer_auth_client):
    response = viewer_auth_client.get("/api/integrations/status")
    assert response.status_code == 403


def test_integration_status_for_it_master(it_auth_client):
    response = it_auth_client.get("/api/integrations/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["microsoft"]["connected"] is False
    assert payload["notion"]["connected"] is False


def test_microsoft_connect_redirects_when_entra_configured(it_auth_client, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-123")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-123")
    from app.config import get_settings

    get_settings.cache_clear()

    response = it_auth_client.get("/api/integrations/microsoft/connect", follow_redirects=False)
    assert response.status_code == 302
    assert "login.microsoftonline.com" in response.headers["location"]


def test_notion_connect_requires_oauth_config(it_auth_client):
    response = it_auth_client.get("/api/integrations/notion/connect", follow_redirects=False)
    assert response.status_code == 400


def test_outlook_status_for_any_user(auth_client):
    response = auth_client.get("/api/integrations/outlook/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is False
    assert "oauth_available" in payload
    assert payload["calendar_enabled"] is False
    assert payload["mail_enabled"] is False


def test_outlook_connect_redirects_when_entra_configured(auth_client, monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant-123")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client-123")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret-123")
    from app.config import get_settings

    get_settings.cache_clear()

    response = auth_client.get("/api/integrations/outlook/connect", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "login.microsoftonline.com" in location
    assert "Calendars.ReadWrite" in location
    assert "Mail.ReadWrite" in location
    assert "Files.Read" in location
    assert "prompt=select_account" in location
    assert "prompt=consent" not in location


def test_outlook_disconnect_when_not_connected(auth_client):
    response = auth_client.delete("/api/integrations/outlook")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_entra_config_save_enables_outlook_oauth(it_auth_client):
    forbidden = it_auth_client  # it_master via IT_ADMIN_EMAILS
    status_before = forbidden.get("/api/integrations/outlook/status")
    assert status_before.status_code == 200
    assert status_before.json()["oauth_available"] is False

    save = forbidden.put(
        "/api/integrations/entra/config",
        json={
            "tenant_id": "tenant-aaa",
            "client_id": "client-bbb",
            "client_secret": "secret-ccc",
        },
    )
    assert save.status_code == 200
    payload = save.json()["entra"]
    assert payload["oauth_available"] is True
    assert payload["source"] == "stored"
    assert payload["tenant_id"] == "tenant-aaa"
    assert payload["client_id"] == "client-bbb"
    assert payload["has_client_secret"] is True

    outlook = forbidden.get("/api/integrations/outlook/status")
    assert outlook.json()["oauth_available"] is True
    assert outlook.json()["oauth_source"] == "stored"

    connect = forbidden.get("/api/integrations/outlook/connect", follow_redirects=False)
    assert connect.status_code == 302
    location = connect.headers["location"]
    assert "login.microsoftonline.com/tenant-aaa" in location
    assert "client-bbb" in location
    assert "Mail.ReadWrite" in location
    assert "prompt=select_account" in location


def test_entra_config_forbidden_for_editor(auth_client):
    response = auth_client.put(
        "/api/integrations/entra/config",
        json={"tenant_id": "t", "client_id": "c", "client_secret": "s"},
    )
    assert response.status_code == 403


def _connect_outlook_for_logged_in_user(*, mail_enabled: bool = True) -> str:
    from app.database import UserAccount, _SessionLocal
    from app.user_integration_store import save_user_integration

    db = _SessionLocal()
    try:
        user = db.scalar(select(UserAccount).where(UserAccount.email == "demo@example.com"))
        assert user is not None
        save_user_integration(
            db,
            user_id=user.id,
            provider="outlook",
            access_token="test-access-token",
            refresh_token="test-refresh",
            expires_at=datetime.now(timezone.utc).replace(year=2099),
            account_label="demo@example.com",
            calendar_enabled=True,
            mail_enabled=mail_enabled,
        )
        return user.id
    finally:
        db.close()


def test_outlook_mail_requires_connection(auth_client):
    response = auth_client.get("/api/integrations/outlook/mail")
    assert response.status_code == 400
    assert response.json()["code"] == "outlook_mail_not_connected"


def test_outlook_mail_list_and_save_for_viewer(viewer_auth_client):
    _connect_outlook_for_logged_in_user()

    listed_messages = [
        {
            "id": "msg-1",
            "subject": "Kiln update {1}",
            "from": {"name": "Anna", "email": "anna@carbonauten.com"},
            "received_at": "2026-09-24T10:00:00Z",
            "preview": "New kiln is online }",
            "is_read": False,
            "has_attachments": False,
            "web_link": "https://outlook.office.com/mail/msg-1",
        }
    ]
    detail = {
        **listed_messages[0],
        "to": [{"name": "Demo", "email": "demo@example.com"}],
        "cc": [],
        "body": "<p>New kiln is online }</p>",
        "body_type": "html",
    }

    with patch(
        "app.routes.integrations.fetch_outlook_messages",
        new=AsyncMock(return_value=listed_messages),
    ), patch(
        "app.outlook_service.get_outlook_message",
        new=AsyncMock(return_value=detail),
    ):
        listed = viewer_auth_client.get("/api/integrations/outlook/mail")
        assert listed.status_code == 200
        messages = listed.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["subject"] == "Kiln update {1}"

        saved = viewer_auth_client.post(
            "/api/integrations/outlook/mail/save",
            json={"message_id": "msg-1", "destination": "both"},
        )
    assert saved.status_code == 200
    payload = saved.json()["saved"]
    assert payload["article"]["title"] == "Kiln update {1}"
    assert payload["article"]["status"] == "draft"
    assert payload["file"]["folder"] == "emails"

    article = viewer_auth_client.get(f"/api/articles/{payload['article']['id']}")
    assert article.status_code == 200
    assert "New kiln is online" in article.json()["article"]["content"]

    files = viewer_auth_client.get("/api/files")
    assert files.status_code == 200
    assert any(item["id"] == payload["file"]["id"] for item in files.json()["files"])


def test_outlook_mail_save_rejects_invalid_destination(auth_client):
    _connect_outlook_for_logged_in_user()
    response = auth_client.post(
        "/api/integrations/outlook/mail/save",
        json={"message_id": "msg-1", "destination": "trash"},
    )
    assert response.status_code == 422
