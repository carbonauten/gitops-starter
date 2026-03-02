import pytest

from flask import request

from app import app, choose_ab_variant


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("AB_VARIANT_A_PERCENT", raising=False)
    yield


def test_ab_endpoint_sets_cookie_and_returns_valid_variant():
    client = app.test_client()

    resp = client.get("/ab-test")

    assert resp.status_code == 200
    body = resp.get_json()
    assert body["experiment"] == "example-service-home"
    assert body["variant"] in {"A", "B"}

    # cookie should be set for stickiness
    cookies = resp.headers.get("Set-Cookie", "")
    assert "ab_variant=" in cookies


def test_choose_ab_variant_uses_env_percentage(monkeypatch):
    # Force 100% A and check result with deterministic random
    monkeypatch.setenv("AB_VARIANT_A_PERCENT", "100")
    with app.test_request_context("/ab-test"):
        # ensure no cookie present
        assert "ab_variant" not in dict(request.cookies)

        variant = choose_ab_variant()
        assert variant == "A"

