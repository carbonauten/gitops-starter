from __future__ import annotations

from unittest.mock import patch


def test_cosine_similarity():
    from app.embedding_service import cosine_similarity

    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0  # mismatched length


def test_semantic_search_returns_empty_without_embeddings_configured(client):
    from app.database import _SessionLocal
    from app.embedding_service import semantic_search_content

    db = _SessionLocal()
    try:
        assert semantic_search_content(db, "irrelevant question") == []
    finally:
        db.close()


def test_embed_text_for_entity_skips_unchanged_text(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.database import _SessionLocal
    from app.embedding_service import embed_text_for_entity

    db = _SessionLocal()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0, 0.0]) as mocked:
            assert embed_text_for_entity(db, entity_type="article", entity_id="a1", text="Hello world") is True
            assert mocked.call_count == 1
            # Same text again -> hash matches, no second API call
            assert embed_text_for_entity(db, entity_type="article", entity_id="a1", text="Hello world") is True
            assert mocked.call_count == 1
            # Different text -> re-embedded
            assert embed_text_for_entity(db, entity_type="article", entity_id="a1", text="Something else") is True
            assert mocked.call_count == 2
    finally:
        db.close()
        get_settings.cache_clear()


def test_reindex_requires_it_master(auth_client):
    response = auth_client.post("/api/search/reindex")
    assert response.status_code == 403


def test_reindex_without_embeddings_configured_is_a_noop(it_auth_client):
    response = it_auth_client.post("/api/search/reindex")
    assert response.status_code == 200
    payload = response.json()
    assert payload["embeddings_available"] is False
    assert payload["counts"] == {"article": 0, "certificate": 0, "file": 0, "skipped": 0, "failed": 0}


def test_reindex_embeds_existing_articles_with_mocked_embeddings(it_auth_client, monkeypatch):
    created = it_auth_client.post(
        "/api/articles",
        json={"title": "Solaranlage Werk 2", "content": "<p>Details zur neuen Solaranlage.</p>", "template": "custom"},
    )
    assert created.status_code == 201

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            response = it_auth_client.post("/api/search/reindex")
        assert response.status_code == 200
        payload = response.json()
        assert payload["embeddings_available"] is True
        assert payload["counts"]["article"] >= 1
        assert payload["counts"]["failed"] == 0
    finally:
        get_settings.cache_clear()


def test_ask_search_merges_semantic_matches_missed_by_keyword_search(it_auth_client, monkeypatch):
    """The actual value-prop: a paraphrased question with zero keyword overlap
    still surfaces the right article once semantic search is wired in."""
    created = it_auth_client.post(
        "/api/articles",
        json={
            "title": "Photovoltaik-Bericht Q3",
            "content": "<p>Die neue Solaranlage produziert seit Juli Strom für das Werk.</p>",
            "template": "custom",
        },
    )
    article_id = created.json()["article"]["id"]

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def fake_embed(text, *, settings=None):
        # Anything mentioning solar energy maps to the same vector as the query below,
        # regardless of exact wording — that's the point of semantic over keyword search.
        needle = "solar" if isinstance(text, str) else ""
        return [1.0, 0.0] if needle in (text or "").lower() else [0.0, 1.0]

    try:
        with patch("app.embedding_service.generate_embedding", side_effect=fake_embed):
            reindex = it_auth_client.post("/api/search/reindex")
            assert reindex.status_code == 200
            assert reindex.json()["counts"]["article"] >= 1

            with patch("app.routes.search.expand_search_query", return_value=None), patch(
                "app.routes.search.generate_search_answer", return_value=None
            ):
                response = it_auth_client.post(
                    "/api/search/ask",
                    json={
                        "question": "Erzeugen wir mittlerweile eigenen Solarstrom?",
                        "language": "de",
                        "type": "article",
                    },
                )
        assert response.status_code == 200
        result_ids = {item["id"] for item in response.json()["results"]}
        assert article_id in result_ids
    finally:
        get_settings.cache_clear()


def test_delete_article_removes_its_embedding(it_auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            created = it_auth_client.post(
                "/api/articles",
                json={"title": "Temp", "content": "<p>Temp content</p>", "template": "custom"},
            )
            article_id = created.json()["article"]["id"]
            it_auth_client.post("/api/search/reindex")

        from app.database import ContentEmbedding, _SessionLocal
        from sqlalchemy import select

        db = _SessionLocal()
        try:
            assert db.scalar(
                select(ContentEmbedding).where(
                    ContentEmbedding.entity_type == "article", ContentEmbedding.entity_id == article_id
                )
            )
        finally:
            db.close()

        deleted = it_auth_client.delete(f"/api/articles/{article_id}")
        assert deleted.status_code == 204

        db = _SessionLocal()
        try:
            assert (
                db.scalar(
                    select(ContentEmbedding).where(
                        ContentEmbedding.entity_type == "article", ContentEmbedding.entity_id == article_id
                    )
                )
                is None
            )
        finally:
            db.close()
    finally:
        get_settings.cache_clear()
