from __future__ import annotations

from unittest.mock import patch


def test_ai_status_without_keys(auth_client):
    response = auth_client.get("/api/ai/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is False
    assert payload["assistant_name"] == "Ask Carbonauten"
    assert "translate" in payload["features"]
    assert "rewrite" in payload["features"]
    assert "draft_from_notes" in payload["features"]
    assert "m365_directory" in payload["features"]


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


def test_rewrite_with_mocked_ai(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    mocked = {
        "title": "China kiln update",
        "content": "<p>The new kiln is online.</p>",
        "tone": "concise",
    }
    with patch("app.routes.ai.rewrite_article", return_value=mocked):
        response = auth_client.post(
            "/api/ai/rewrite",
            json={
                "title": "Update China Ofen",
                "content": "<p>Neuer Ofen ist online gegangen und läuft gut.</p>",
                "tone": "concise",
                "language": "en",
            },
        )
    assert response.status_code == 200
    assert response.json()["rewrite"]["tone"] == "concise"
    assert "kiln" in response.json()["rewrite"]["title"].lower()
    get_settings.cache_clear()


def test_draft_from_notes_with_mocked_ai(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    mocked = {
        "title": "Weekly ops note",
        "content": "<p>Kiln online.</p><ul><li>ISO audit next week</li></ul>",
        "language": "en",
    }
    with patch("app.routes.ai.draft_article_from_notes", return_value=mocked):
        response = auth_client.post(
            "/api/ai/draft-from-notes",
            json={
                "notes": "- kiln online\n- ISO audit next week",
                "language": "en",
                "title_hint": "Ops",
            },
        )
    assert response.status_code == 200
    assert response.json()["draft"]["title"] == "Weekly ops note"
    assert "<ul>" in response.json()["draft"]["content"]
    get_settings.cache_clear()


def test_rewrite_rejects_invalid_tone(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    response = auth_client.post(
        "/api/ai/rewrite",
        json={"title": "A", "content": "<p>B</p>", "tone": "sarcastic"},
    )
    assert response.status_code == 422
    get_settings.cache_clear()


def test_search_ask_includes_assistant_name(auth_client):
    auth_client.post("/api/articles", json={"title": "Biochar Update", "content": "New kiln online"})
    response = auth_client.post(
        "/api/search/ask",
        json={"question": "biochar kiln status", "language": "en"},
    )
    assert response.status_code == 200
    assert response.json()["assistant_name"] == "Ask Carbonauten"
