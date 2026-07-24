from __future__ import annotations

from unittest.mock import patch

import pytest


def test_ai_status_without_keys(auth_client):
    response = auth_client.get("/api/ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["assistant_name"] == "Ask Carbonauten"
    assert "translate" in payload["features"]


def test_translate_requires_ai(auth_client):
    response = auth_client.post(
        "/api/ai/translate",
        json={
            "title": "Hallo",
            "content": "<p>Welt</p>",
            "target_language": "en",
        },
    )
    assert response.status_code == 503


def test_translate_with_mocked_ai(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    mocked = {
        "title": "Hello",
        "content": "<p>World</p>",
        "target_language": "en",
    }
    with patch("app.routes.ai.translate_article", return_value=mocked):
        response = auth_client.post(
            "/api/ai/translate",
            json={
                "title": "Hallo",
                "content": "<p>Welt</p>",
                "target_language": "en",
            },
        )
    assert response.status_code == 200
    assert response.json()["translation"]["title"] == "Hello"
    get_settings.cache_clear()


def test_summarize_with_mocked_ai(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    with patch("app.routes.ai.summarize_article", return_value="- Point one\n- Point two"):
        response = auth_client.post(
            "/api/ai/summarize",
            json={
                "title": "Weekly Update",
                "content": "<p>Production ramp-up in China</p>",
                "language": "en",
            },
        )
    assert response.status_code == 200
    assert "Point one" in response.json()["summary"]
    get_settings.cache_clear()


def test_search_ask_includes_assistant_name(auth_client):
    auth_client.post("/api/articles", json={"title": "Biochar Update", "content": "New kiln online"})
    response = auth_client.post(
        "/api/search/ask",
        json={"question": "biochar kiln status", "language": "en"},
    )
    assert response.status_code == 200
    assert response.json()["assistant_name"] == "Ask Carbonauten"
