from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.database import Article, Certificate, SyncLog
from app.sync_service import export_sync_payload, import_sync_payload, sync_status


def _get_db():
    from app.config import get_settings
    from app.database import _SessionLocal, init_database

    if _SessionLocal is None:
        init_database(get_settings().effective_database_url)
    from app.database import _SessionLocal as session_factory

    return session_factory()


def _seed_article(title: str = "Sync Article") -> str:
    db = _get_db()
    try:
        article = Article(
            title=title,
            content="<p>sync</p>",
            status="published",
            author_id="author-1",
            author_name="Author",
            author_email="author@example.com",
        )
        db.add(article)
        db.commit()
        db.refresh(article)
        return article.id
    finally:
        db.close()


def _seed_certificate(name: str = "ISO 9001") -> str:
    db = _get_db()
    try:
        certificate = Certificate(
            name=name,
            category="compliance",
            issuer="TUV",
            valid_from=date(2025, 1, 1),
            valid_to=date(2027, 1, 1),
            created_by_id="user-1",
            created_by_name="Admin",
        )
        db.add(certificate)
        db.commit()
        db.refresh(certificate)
        return certificate.id
    finally:
        db.close()


def test_health_includes_region_fields(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deployment_region"] == "eu"
    assert payload["storage_backend"] == "local"
    assert payload["sync_configured"] is False


def test_sync_status_requires_it_master(auth_client):
    response = auth_client.get("/api/sync/status")
    assert response.status_code == 403


def test_sync_status_for_it_master(it_auth_client):
    response = it_auth_client.get("/api/sync/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["region"] == "eu"
    assert payload["sync_enabled"] is False


def test_sync_export_requires_api_key(it_auth_client):
    response = it_auth_client.get("/api/sync/export")
    assert response.status_code == 401


def test_sync_export_and_import(monkeypatch, it_auth_client):
    monkeypatch.setenv("SYNC_API_KEY", "test-sync-key")
    from app.config import get_settings

    get_settings.cache_clear()

    article_id = _seed_article()
    certificate_id = _seed_certificate()

    export_response = it_auth_client.get("/api/sync/export", headers={"X-Sync-Key": "test-sync-key"})
    assert export_response.status_code == 200
    payload = export_response.json()
    assert payload["region"] == "eu"
    assert any(item["id"] == article_id for item in payload["articles"])
    assert any(item["id"] == certificate_id for item in payload["certificates"])

    import_payload = dict(payload)
    import_payload["region"] = "cn"
    import_response = it_auth_client.post(
        "/api/sync/import",
        headers={"X-Sync-Key": "test-sync-key"},
        json=import_payload,
    )
    assert import_response.status_code == 200
    result = import_response.json()
    assert result["articles"]["created"] >= 0
    assert result["certificates"]["created"] >= 0

    get_settings.cache_clear()


def test_import_same_region_rejected(it_auth_client, monkeypatch):
    monkeypatch.setenv("SYNC_API_KEY", "test-sync-key")
    from app.config import get_settings

    get_settings.cache_clear()

    db = _get_db()
    try:
        payload = export_sync_payload(db)
    finally:
        db.close()

    response = it_auth_client.post(
        "/api/sync/import",
        headers={"X-Sync-Key": "test-sync-key"},
        json=payload,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "sync_same_region"
    get_settings.cache_clear()


def test_sync_service_upsert_last_write_wins():
    db = _get_db()
    try:
        article = Article(
            id="article-sync-1",
            title="Local",
            content="local",
            status="draft",
            author_id="a",
            author_name="A",
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        db.add(article)
        db.commit()

        payload = {
            "region": "cn",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "articles": [
                {
                    "id": "article-sync-1",
                    "title": "Remote",
                    "content": "remote",
                    "status": "published",
                    "template": None,
                    "author_id": "b",
                    "author_name": "B",
                    "author_email": "b@example.com",
                    "created_at": "2025-01-01T00:00:00+00:00",
                    "updated_at": "2026-06-01T00:00:00+00:00",
                }
            ],
            "certificates": [],
        }
        result = import_sync_payload(db, payload)
        assert result["articles"]["updated"] == 1
        updated = db.get(Article, "article-sync-1")
        assert updated.title == "Remote"
    finally:
        db.close()


def test_sync_status_counts():
    _seed_article("Count A")
    _seed_certificate("Count Cert")
    db = _get_db()
    try:
        status = sync_status(db)
        assert status["article_count"] >= 1
        assert status["certificate_count"] >= 1
        entry = SyncLog(direction="pull", status="success", article_count=1, certificate_count=1)
        db.add(entry)
        db.commit()
        status = sync_status(db)
        assert status["last_success_at"] is not None
    finally:
        db.close()
