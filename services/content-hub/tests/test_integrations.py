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
