from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.strato_automation_service import STEP_UNEXPECTED, StratoAutomationError, create_mailbox_via_automation


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


def test_save_and_parse_known_domains(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    saved = it_auth_client.put(
        "/api/strato-automation/domains",
        json={"domains": "carbonauten.com, Fuckco2.shop\ncarbonauten.com"},
    )
    assert saved.status_code == 200
    payload = saved.json()
    # mixed separators, mixed case and a duplicate all normalize correctly
    assert payload["domains"] == ["carbonauten.com", "fuckco2.shop"]
    assert payload["domains_raw"] == "carbonauten.com, Fuckco2.shop\ncarbonauten.com"

    status = it_auth_client.get("/api/strato-automation/status")
    assert status.json()["domains"] == ["carbonauten.com", "fuckco2.shop"]

    it_auth_client.delete("/api/strato-automation/config")


def test_save_domains_requires_config_first(it_auth_client):
    response = it_auth_client.put("/api/strato-automation/domains", json={"domains": "carbonauten.com"})
    assert response.status_code == 400


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


def test_create_mailbox_wraps_browser_launch_failure(it_auth_client):
    # Regression test: a failure launching/setting up the browser itself
    # (missing Chromium binary, OOM, ...) must still come out as a
    # StratoAutomationError, not an unhandled exception that bypasses the
    # route's translated-error handling entirely.
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    class FakeChromium:
        @staticmethod
        async def launch(headless=True):
            raise RuntimeError("Executable doesn't exist (simulated)")

    class FakePlaywright:
        chromium = FakeChromium()

        async def stop(self):
            pass

    class FakePlaywrightStarter:
        async def start(self):
            return FakePlaywright()

    def fake_async_playwright():
        return FakePlaywrightStarter()

    from app.database import _SessionLocal

    db = _SessionLocal()
    try:
        with patch("playwright.async_api.async_playwright", fake_async_playwright):
            with pytest.raises(StratoAutomationError) as exc_info:
                asyncio.run(
                    create_mailbox_via_automation(
                        db,
                        local_part="sales",
                        domain="carbonauten.com",
                        password="a-strong-password-1",
                    )
                )
        assert exc_info.value.code == STEP_UNEXPECTED
    finally:
        db.close()

    it_auth_client.delete("/api/strato-automation/config")


def test_create_mailbox_success(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    async def _fake_create(*args, **kwargs):
        return {"status": "created", "email": "sales@carbonauten.com", "local_part": "sales", "domain": "carbonauten.com"}

    with patch("app.routes.strato_automation.create_mailbox_via_automation", side_effect=_fake_create):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox",
            json={"local_part": "sales", "domain": "carbonauten.com", "password": "a-strong-password-1"},
        )
    assert response.status_code == 200
    assert response.json()["mailbox"]["email"] == "sales@carbonauten.com"

    it_auth_client.delete("/api/strato-automation/config")


def test_create_mailbox_surfaces_captcha_required(it_auth_client):
    # Strato's login form shows a CAPTCHA for this account - the route must
    # pass this through as a normal 200 response (a human needs to solve
    # it), not treat it as a failure or log a create_failed audit entry.
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    async def _fake_create(*args, **kwargs):
        return {"status": "captcha_required", "session_id": "abc123", "captcha_image_base64": "ZmFrZS1pbWFnZQ=="}

    with patch("app.routes.strato_automation.create_mailbox_via_automation", side_effect=_fake_create):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox",
            json={"local_part": "sales", "domain": "carbonauten.com", "password": "a-strong-password-1"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "captcha_required"
    assert payload["session_id"] == "abc123"
    assert payload["captcha_image_base64"] == "ZmFrZS1pbWFnZQ=="

    it_auth_client.delete("/api/strato-automation/config")


def test_resume_create_mailbox_with_captcha_success(it_auth_client):
    async def _fake_resume(session_id, captcha_code):
        assert session_id == "abc123"
        assert captcha_code == "0802"
        return {"status": "created", "email": "sales@carbonauten.com", "local_part": "sales", "domain": "carbonauten.com"}

    with patch("app.routes.strato_automation.resume_create_mailbox_via_automation", side_effect=_fake_resume):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox/captcha",
            json={"session_id": "abc123", "captcha_code": "0802"},
        )
    assert response.status_code == 200
    assert response.json()["mailbox"]["email"] == "sales@carbonauten.com"


def test_resume_create_mailbox_with_wrong_captcha_surfaces_error(it_auth_client):
    async def _fake_resume(session_id, captcha_code):
        raise StratoAutomationError("strato_automation_2fa_or_captcha", "ZmFrZQ==")

    with patch("app.routes.strato_automation.resume_create_mailbox_via_automation", side_effect=_fake_resume):
        response = it_auth_client.post(
            "/api/strato-automation/create-mailbox/captcha",
            json={"session_id": "abc123", "captcha_code": "wrong"},
        )
    assert response.status_code == 502
    assert response.json()["code"] == "strato_automation_2fa_or_captcha"


def test_editor_cannot_resume_captcha(auth_client):
    response = auth_client.post(
        "/api/strato-automation/create-mailbox/captcha",
        json={"session_id": "abc123", "captcha_code": "0802"},
    )
    assert response.status_code == 403
