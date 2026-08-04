from app.config import get_settings
from app.shop_bot_protection import reset_rate_limits_for_tests


def test_shop_config_exposes_bot_protection(client):
    response = client.get("/api/shop/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["analytics_enabled"] is True
    assert payload["bot_protection"]["enabled"] is True
    assert payload["bot_protection"]["turnstile_required"] is False
    assert payload["bot_protection"]["turnstile_site_key"] == ""


def test_honeypot_blocks_register(client):
    reset_rate_limits_for_tests()
    response = client.post(
        "/api/shop/auth/register",
        json={
            "email": "bot@example.com",
            "name": "Bot",
            "password": "password123",
            "website": "https://spam.example",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "bot_detected"


def test_honeypot_blocks_pageview(client):
    reset_rate_limits_for_tests()
    response = client.post(
        "/api/shop/analytics/pageview",
        json={
            "path": "/",
            "session_id": "session-abc-12345",
            "website": "http://evil.test",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "bot_detected"


def test_pageview_and_monitoring_summary(auth_client, client):
    reset_rate_limits_for_tests()
    recorded = client.post(
        "/api/shop/analytics/pageview",
        json={
            "path": "/p/biochar",
            "referrer": "https://google.com",
            "session_id": "session-monitor-1",
            "website": "",
        },
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert recorded.status_code == 200
    assert recorded.json()["recorded"] is True

    home = client.post(
        "/api/shop/analytics/pageview",
        json={"path": "/", "session_id": "session-monitor-2", "website": ""},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert home.status_code == 200

    summary = auth_client.get("/api/shop/monitoring/summary?days=7")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["views_period"] >= 2
    assert payload["views_today"] >= 2
    assert any(item["path"] == "/p/biochar" for item in payload["top_paths"])
    assert any(item["ip"] == "203.0.113.50" for item in payload["top_ips"])
    assert any(item.get("ip_address") == "203.0.113.50" for item in payload["recent"])
    assert len(payload["by_day"]) == 7
    assert len(payload["recent"]) >= 2


def test_monitoring_requires_auth(client):
    response = client.get("/api/shop/monitoring/summary")
    assert response.status_code == 401


def test_auth_rate_limit(client, monkeypatch):
    reset_rate_limits_for_tests()
    monkeypatch.setenv("SHOP_BOT_AUTH_RATE_LIMIT", "3")
    monkeypatch.setenv("SHOP_BOT_RATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()

    for index in range(3):
        response = client.post(
            "/api/shop/auth/login",
            json={"email": f"nope{index}@example.com", "password": "wrong-password", "website": ""},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/shop/auth/login",
        json={"email": "nope-final@example.com", "password": "wrong-password", "website": ""},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"
    get_settings.cache_clear()
    reset_rate_limits_for_tests()
