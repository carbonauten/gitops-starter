from unittest.mock import patch

from app.mailcow_service import reset_mock_mailboxes


def setup_function() -> None:
    reset_mock_mailboxes()


def teardown_function() -> None:
    reset_mock_mailboxes()


def test_editor_cannot_access_mail_server(auth_client):
    response = auth_client.get("/api/mail-server/status")
    assert response.status_code == 403


def test_it_master_sees_mock_status_without_config(it_auth_client):
    response = it_auth_client.get("/api/mail-server/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mock"] is True
    assert payload["configured"] is False


def test_it_master_lists_mock_mailboxes(it_auth_client):
    response = it_auth_client.get("/api/mail-server/mailboxes", params={"domain": "carbonauten.com"})
    assert response.status_code == 200
    emails = {box["email"] for box in response.json()["mailboxes"]}
    assert "info@carbonauten.com" in emails


def test_it_master_creates_and_deletes_mock_mailbox(it_auth_client):
    created = it_auth_client.post(
        "/api/mail-server/mailboxes",
        json={
            "local_part": "sales",
            "domain": "carbonauten.com",
            "display_name": "Sales",
            "password": "a-strong-password-1",
        },
    )
    assert created.status_code == 201
    mailbox = created.json()["mailbox"]
    assert mailbox["email"] == "sales@carbonauten.com"

    listing = it_auth_client.get("/api/mail-server/mailboxes", params={"domain": "carbonauten.com"})
    assert any(box["email"] == "sales@carbonauten.com" for box in listing.json()["mailboxes"])

    deleted = it_auth_client.delete("/api/mail-server/mailboxes/sales@carbonauten.com")
    assert deleted.status_code == 204

    listing_after = it_auth_client.get("/api/mail-server/mailboxes", params={"domain": "carbonauten.com"})
    assert not any(box["email"] == "sales@carbonauten.com" for box in listing_after.json()["mailboxes"])


def test_cannot_create_duplicate_mock_mailbox(it_auth_client):
    response = it_auth_client.post(
        "/api/mail-server/mailboxes",
        json={
            "local_part": "info",
            "domain": "carbonauten.com",
            "display_name": "Info",
            "password": "a-strong-password-1",
        },
    )
    assert response.status_code == 409


def test_create_mailbox_rejects_invalid_local_part(it_auth_client):
    response = it_auth_client.post(
        "/api/mail-server/mailboxes",
        json={
            "local_part": "not valid!",
            "domain": "carbonauten.com",
            "password": "a-strong-password-1",
        },
    )
    assert response.status_code == 400


def test_save_and_clear_stored_config(it_auth_client):
    saved = it_auth_client.put(
        "/api/mail-server/config",
        json={
            "api_url": "https://mail.carbonauten.com",
            "api_key": "test-mailcow-key",
            "default_domain": "carbonauten.com",
        },
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["source"] == "stored"
    assert payload["api_url"] == "https://mail.carbonauten.com"
    assert payload["default_domain"] == "carbonauten.com"

    cleared = it_auth_client.delete("/api/mail-server/config")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False


def test_create_mailbox_calls_real_mailcow_api_when_configured(it_auth_client):
    it_auth_client.put(
        "/api/mail-server/config",
        json={
            "api_url": "https://mail.carbonauten.com",
            "api_key": "test-mailcow-key",
            "default_domain": "carbonauten.com",
        },
    )

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return [{"type": "success", "msg": "mailbox_added"}]

    class FakeMailcowClient:
        """Standalone fake, not a real httpx.Client - patching httpx.Client.post
        directly would also hijack the TestClient's own httpx-based transport."""

        def __init__(self):
            self.post_calls: list[tuple[str, dict]] = []

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def post(self, path, json):
            self.post_calls.append((path, json))
            return FakeResponse()

    fake_client = FakeMailcowClient()
    with patch("app.mailcow_service._client", return_value=fake_client):
        response = it_auth_client.post(
            "/api/mail-server/mailboxes",
            json={
                "local_part": "newuser",
                "domain": "carbonauten.com",
                "display_name": "New User",
                "password": "a-strong-password-1",
            },
        )
    assert response.status_code == 201
    assert response.json()["mailbox"]["email"] == "newuser@carbonauten.com"
    assert len(fake_client.post_calls) == 1
    path, body = fake_client.post_calls[0]
    assert path == "/api/v1/add/mailbox"
    assert body["local_part"] == "newuser"
    assert body["domain"] == "carbonauten.com"

    it_auth_client.delete("/api/mail-server/config")
