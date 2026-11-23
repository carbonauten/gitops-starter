from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.wordpress_automation_service import (
    STEP_UNEXPECTED,
    WordPressAutomationError,
    install_wordpress_via_automation,
)


def test_editor_cannot_access_wordpress(auth_client):
    response = auth_client.get("/api/wordpress/status")
    assert response.status_code == 403


def test_viewer_cannot_access_wordpress(viewer_auth_client):
    response = viewer_auth_client.get("/api/wordpress/status")
    assert response.status_code == 403


def test_designer_sees_unconfigured_status(designer_auth_client):
    response = designer_auth_client.get("/api/wordpress/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_it_master_sees_unconfigured_status(it_auth_client):
    response = it_auth_client.get("/api/wordpress/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_wordpress_reuses_strato_automation_config(designer_auth_client):
    # WordPress automation has no config endpoints of its own - it reads the
    # same stored Strato customer login that /api/strato-automation/config
    # writes. A designer can't write that config (it_master-only), but can
    # see it reflected once an it_master has saved it.
    saved = designer_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )
    assert saved.status_code == 403

    status = designer_auth_client.get("/api/wordpress/status")
    assert status.status_code == 200
    assert status.json()["configured"] is False


def test_list_installations_requires_config_first(designer_auth_client):
    # No patching here - the real service function's "not configured" check
    # runs before any Playwright import, exercising the real code path
    # without needing a browser.
    response = designer_auth_client.get("/api/wordpress/installations")
    assert response.status_code == 400


def test_install_requires_config_first(designer_auth_client):
    response = designer_auth_client.post(
        "/api/wordpress/install",
        json={"mode": "flexibility", "domain": "carbonauten.com"},
    )
    assert response.status_code == 400


def test_install_rejects_unknown_mode(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )
    response = it_auth_client.post(
        "/api/wordpress/install",
        json={"mode": "not-a-real-mode", "domain": "carbonauten.com"},
    )
    assert response.status_code == 400

    it_auth_client.delete("/api/strato-automation/config")


def test_list_installations_surfaces_automation_error_with_screenshot(designer_auth_client):
    designer_put = designer_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )
    assert designer_put.status_code == 403
    # Seed config as it_master instead (designer can't write it), then
    # continue exercising the designer's read/list access below.
    from app.database import PlatformStratoSettings, _SessionLocal
    from app.user_integration_store import encrypt_secret

    db = _SessionLocal()
    try:
        row = PlatformStratoSettings(id="default", customer_number="74845696", password_enc=encrypt_secret("x"))
        db.merge(row)
        db.commit()
    finally:
        db.close()

    async def _fake_list(*args, **kwargs):
        raise WordPressAutomationError("wordpress_automation_login_failed", "ZmFrZS1zY3JlZW5zaG90")

    with patch("app.routes.wordpress.list_wordpress_installations", side_effect=_fake_list):
        response = designer_auth_client.get("/api/wordpress/installations")
    assert response.status_code == 502
    payload = response.json()
    assert payload["code"] == "wordpress_automation_login_failed"
    assert payload["screenshot_base64"] == "ZmFrZS1zY3JlZW5zaG90"


def test_install_success(it_auth_client):
    it_auth_client.put(
        "/api/strato-automation/config",
        json={"customer_number": "74845696", "password": "test-strato-password"},
    )

    async def _fake_install(*args, **kwargs):
        return {"domain": "carbonauten.com", "mode": "security"}

    with patch("app.routes.wordpress.install_wordpress_via_automation", side_effect=_fake_install):
        response = it_auth_client.post(
            "/api/wordpress/install",
            json={"mode": "security", "domain": "carbonauten.com"},
        )
    assert response.status_code == 200
    assert response.json()["installation"]["domain"] == "carbonauten.com"

    it_auth_client.delete("/api/strato-automation/config")


def test_install_wraps_browser_launch_failure():
    # Regression test: a failure launching/setting up the browser itself
    # must still come out as a WordPressAutomationError, not an unhandled
    # exception that bypasses the route's translated-error handling.
    from app.database import PlatformStratoSettings, _SessionLocal
    from app.user_integration_store import encrypt_secret

    db = _SessionLocal()
    try:
        row = PlatformStratoSettings(id="default", customer_number="74845696", password_enc=encrypt_secret("x"))
        db.merge(row)
        db.commit()

        class FakeChromium:
            @staticmethod
            async def launch(headless=True):
                raise RuntimeError("Executable doesn't exist (simulated)")

        class FakePw:
            chromium = FakeChromium()

        class FakePlaywrightContextManager:
            async def __aenter__(self):
                return FakePw()

            async def __aexit__(self, *exc_info):
                return False

        def fake_async_playwright():
            return FakePlaywrightContextManager()

        with patch("playwright.async_api.async_playwright", fake_async_playwright):
            with pytest.raises(WordPressAutomationError) as exc_info:
                asyncio.run(
                    install_wordpress_via_automation(db, mode="security", domain="carbonauten.com")
                )
        assert exc_info.value.code == STEP_UNEXPECTED
    finally:
        db.delete(db.get(PlatformStratoSettings, "default"))
        db.commit()
        db.close()
