import pytest


def test_search_returns_grouped_counts(auth_client):
    auth_client.post("/api/articles", json={"title": "Weekly Update", "content": "Production news"})
    auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO 9001",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-12-31",
            "responsible_name": "QA",
            "responsible_email": "qa@example.com",
        },
    )

    response = auth_client.get("/api/search", params={"q": "ISO"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["certificate"] >= 1
    assert any(item["type"] == "certificate" for item in payload["results"])
    assert "ai_available" in payload


def test_search_type_filter(auth_client):
    auth_client.post("/api/articles", json={"title": "Filter Article", "content": "UniqueAlphaContent"})
    auth_client.post(
        "/api/certificates",
        json={
            "name": "UniqueAlphaCert",
            "category": "ssl",
            "issuer": "CA",
            "valid_from": "2025-01-01",
            "valid_to": "2026-12-31",
            "responsible_name": "Ops",
            "responsible_email": "ops@example.com",
        },
    )

    response = auth_client.get("/api/search", params={"q": "UniqueAlpha", "type": "article"})
    assert response.status_code == 200
    payload = response.json()
    assert all(item["type"] == "article" for item in payload["results"])


def test_search_suggestions(auth_client):
    auth_client.post("/api/articles", json={"title": "Suggestion Title", "content": "Body"})
    response = auth_client.get("/api/search/suggestions")
    assert response.status_code == 200
    assert "Suggestion Title" in response.json()["suggestions"]


def test_search_ask_keyword_mode(auth_client):
    auth_client.post("/api/articles", json={"title": "Ask Target", "content": "Answer lives here"})
    response = auth_client.post(
        "/api/search/ask",
        json={"question": "Where is the answer?", "language": "en"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] in {"keyword", "ai"}
    assert payload["answer"]
    assert any(item["title"] == "Ask Target" for item in payload["results"])
