from datetime import datetime, timedelta, timezone

from app.database import Article
from app.workflow_service import process_due_scheduled_articles


def test_article_workflow_submit_approve(auth_client, it_auth_client):
    create = auth_client.post("/api/articles", json={"title": "Workflow", "content": "<p>x</p>"})
    assert create.status_code == 201
    article_id = create.json()["article"]["id"]

    submit = auth_client.post(f"/api/workflow/articles/{article_id}/submit")
    assert submit.status_code == 200
    assert submit.json()["article"]["status"] == "review"

    editor_update = auth_client.patch(f"/api/articles/{article_id}", json={"title": "Blocked"})
    assert editor_update.status_code == 400

    approve = it_auth_client.post(f"/api/workflow/articles/{article_id}/approve", json={})
    assert approve.status_code == 200
    assert approve.json()["article"]["status"] == "published"


def test_article_workflow_reject(auth_client, it_auth_client):
    create = auth_client.post("/api/articles", json={"title": "Reject me", "content": ""})
    article_id = create.json()["article"]["id"]
    auth_client.post(f"/api/workflow/articles/{article_id}/submit")

    reject = it_auth_client.post(
        f"/api/workflow/articles/{article_id}/reject",
        json={"comment": "Needs more detail"},
    )
    assert reject.status_code == 200
    assert reject.json()["article"]["status"] == "rejected"
    assert reject.json()["article"]["review_comment"] == "Needs more detail"


def _get_db():
    from app.config import get_settings
    from app.database import _SessionLocal, init_database

    if _SessionLocal is None:
        init_database(get_settings().effective_database_url)
    from app.database import _SessionLocal as session_factory

    return session_factory()


def test_article_scheduled_publish(it_auth_client, monkeypatch):
    create = it_auth_client.post("/api/articles", json={"title": "Scheduled", "content": "c"})
    article_id = create.json()["article"]["id"]
    it_auth_client.post(f"/api/workflow/articles/{article_id}/submit")

    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    approve = it_auth_client.post(
        f"/api/workflow/articles/{article_id}/approve",
        json={"scheduled_publish_at": future},
    )
    assert approve.status_code == 200
    assert approve.json()["article"]["status"] == "scheduled"

    db = _get_db()
    try:
        article = db.get(Article, article_id)
        article.scheduled_publish_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        published = process_due_scheduled_articles(db)
        assert published == 1
        article = db.get(Article, article_id)
        assert article.status == "published"
    finally:
        db.close()


def test_publish_requires_published_status(auth_client, it_auth_client):
    create = auth_client.post("/api/articles", json={"title": "Draft pub", "content": "x"})
    article_id = create.json()["article"]["id"]

    blocked = auth_client.post(f"/api/publish/articles/{article_id}", json={"channels": ["teams"]})
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "article_not_published"

    auth_client.post(f"/api/workflow/articles/{article_id}/submit")
    it_auth_client.post(f"/api/workflow/articles/{article_id}/approve", json={})

    ok = auth_client.post(f"/api/publish/articles/{article_id}", json={"channels": ["teams"]})
    assert ok.status_code == 200


def test_certificate_renewal_workflow(auth_client, it_auth_client):
    cert = auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO",
            "category": "compliance",
            "issuer": "TUV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-01-01",
            "renewal_in_progress": True,
        },
    )
    cert_id = cert.json()["certificate"]["id"]

    blocked = auth_client.post(f"/api/workflow/certificates/{cert_id}/request-renewal")
    assert blocked.status_code == 200

    pending = it_auth_client.get("/api/workflow/pending")
    assert any(item["id"] == cert_id for item in pending.json()["certificate_renewals_pending"])

    approve = it_auth_client.post(f"/api/workflow/certificates/{cert_id}/approve-renewal")
    assert approve.status_code == 200
    assert approve.json()["certificate"]["renewal_approval_status"] == "approved"


def test_audit_log_for_article_create(auth_client, it_auth_client):
    create = auth_client.post("/api/articles", json={"title": "Audited", "content": ""})
    assert create.status_code == 201

    audit = it_auth_client.get("/api/audit")
    assert audit.status_code == 200
    entries = audit.json()["entries"]
    assert any(entry["action"] == "create" and entry["entity_type"] == "article" for entry in entries)


def test_audit_requires_it_master(auth_client):
    response = auth_client.get("/api/audit")
    assert response.status_code == 403


def test_monitor_summary(it_auth_client):
    response = it_auth_client.get("/api/monitor/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "audit_entry_count" in payload
