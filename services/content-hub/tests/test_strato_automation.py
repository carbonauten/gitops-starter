from __future__ import annotations

from unittest.mock import patch

from app.strato_automation_service import StratoAutomationError


def test_editor_cannot_access_strato_automation(auth_client):
    response = auth_client.get("/api/strato-automation/status")
    assert response.status_code == 403


def test_it_master_sees_unconfigured_status(it_auth_client):
    response = it_auth_client.get("/api/strato-automation/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_save_and_clear_strato_config(it_auth_client):
    saved = it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["configured"] is True
    assert payload["customer_number"] == "74845696"

    cleared = it_auth_client.delete("/api/strato-automation/config")
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False


def test_create_mailbox_requires_config_first(it_auth_client):
    # No patching here - the real service function's "not configured" check
    # runs before any Playwright import, so this exercises the real code path
    # without needing a browser.
    response = it_auth_client.post(
        "/api/strato-automation/create-mailbox",
        json={"local_part": "sales", "domain": "carbonauten.com", "password": "a-strong-password-1"},
    )
    assert response.status_code == 400


def test_create_mailbox_surfaces_automation_error_with_screenshot(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    async def _fake_create(*args, **kwargs):
        raise StratoAutomationError("strato_automation_login_failed", "ZmFrZS1zY3JlZW5zaG90")

    with patch("app.routes.strato_automation.create_mailbox_via_automation", side_effect=_fake_create):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox",
            json={"local_part": "sales", "domain": "carbonauten.com", "password": "a-strong-password-1"},
        )
    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "strato_automation_login_failed"
    assert payload["screenshot_base64"] == "ZmFrZS1zY3JlZW5zaG90"

    it_auth_client.delete("/api/strato-automation/config")


def test_create_mailbox_success(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    async def _fake_create(*args, **kwargs):
        return {"email": "sales@carbonauten.com", "local_part": "sales", "domain": "carbonauten.com"}

    with patch("app.routes.strato_automation.create_mailbox_via_automation", side_effect=_fake_create):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox",
            json={"local_part": "sales", "domain": "carbonauten.com", "password": "a-strong-password-1"},
        )
    assert response.status_code == 200
    assert response.json()["mailbox"]["email"] == "sales@carbonauten.com"

    it_auth_client.delete("/api/strato-automation/config")
