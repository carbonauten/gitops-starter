"""Regression tests for the bug-scan fixes on top of Sprint P (semantic search):

1. embed_text_for_entity() must re-embed on an embedding-model change, not just a text change.
2. SharePoint certificate import must queue a re-embed (for both the certificate and its file).
3. SharePoint standalone file import must queue a re-embed.
4. SSL cert auto-import (upsert_ssl_certificate) must embed the certificate it creates/updates.
5. Cross-region sync (import_sync_payload) must embed the articles/certificates it syncs in.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from sqlalchemy import select


def _has_embedding(entity_type: str, entity_id: str) -> bool:
    from app.database import ContentEmbedding, _SessionLocal

    db = _SessionLocal()
    try:
        return (
            db.scalar(
                select(ContentEmbedding).where(
                    ContentEmbedding.entity_type == entity_type, ContentEmbedding.entity_id == entity_id
                )
            )
            is not None
        )
    finally:
        db.close()


def test_embed_text_for_entity_reembeds_on_model_change(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "model-a")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.database import _SessionLocal
    from app.embedding_service import embed_text_for_entity

    db = _SessionLocal()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]) as mocked:
            assert embed_text_for_entity(db, entity_type="article", entity_id="m1", text="same text") is True
            assert mocked.call_count == 1

            # Same text again, same model -> skipped (existing behavior, unchanged)
            assert embed_text_for_entity(db, entity_type="article", entity_id="m1", text="same text") is True
            assert mocked.call_count == 1

        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "model-b")
        get_settings.cache_clear()
        with patch("app.embedding_service.generate_embedding", return_value=[0.0, 1.0]) as mocked:
            # Same text, different configured model -> must re-embed, not skip
            assert embed_text_for_entity(db, entity_type="article", entity_id="m1", text="same text") is True
            assert mocked.call_count == 1
    finally:
        db.close()
        get_settings.cache_clear()


def test_sharepoint_certificate_import_embeds_certificate_and_file(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            response = auth_client.post(
                "/api/certificates/import-from-sharepoint",
                json={"item_id": "sp-file-cert-iso9001"},
            )
        assert response.status_code == 201
        certificate = response.json()["certificate"]
        assert _has_embedding("certificate", certificate["id"])
        assert _has_embedding("file", certificate["file_asset_id"])
    finally:
        get_settings.cache_clear()


def test_sharepoint_file_import_embeds_file(auth_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            response = auth_client.post(
                "/api/files/import-from-sharepoint",
                json={"item_id": "sp-file-cert-iso9001", "folder": "certificates"},
            )
        assert response.status_code == 201
        file_id = response.json()["file"]["id"]
        assert _has_embedding("file", file_id)
    finally:
        get_settings.cache_clear()


def test_ssl_import_embeds_certificate(auth_client, monkeypatch):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "embed-test.example.com")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=90))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            response = auth_client.post(
                "/api/certificates/import-ssl",
                files={"upload": ("embed-test.pem", BytesIO(pem), "application/x-pem-file")},
            )
        assert response.status_code == 201
        certificate_id = response.json()["certificate"]["id"]
        assert _has_embedding("certificate", certificate_id)
    finally:
        get_settings.cache_clear()


def test_cross_region_sync_embeds_synced_content(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    from app.database import _SessionLocal
    from app.sync_service import import_sync_payload

    db = _SessionLocal()
    try:
        payload = {
            "region": "cn",
            "exported_at": "2026-01-01T00:00:00+00:00",
            "articles": [
                {
                    "id": "sync-article-1",
                    "title": "Synced Article",
                    "content": "<p>Content from the peer region.</p>",
                    "status": "published",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
            "certificates": [
                {
                    "id": "sync-cert-1",
                    "name": "Synced Certificate",
                    "category": "compliance",
                    "issuer": "Peer Issuer",
                    "valid_from": "2026-01-01",
                    "valid_to": "2027-01-01",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        }
        with patch("app.embedding_service.generate_embedding", return_value=[1.0, 0.0]):
            result = import_sync_payload(db, payload)
        assert result["articles"]["created"] == 1
        assert result["certificates"]["created"] == 1
    finally:
        db.close()
        get_settings.cache_clear()

    assert _has_embedding("article", "sync-article-1")
    assert _has_embedding("certificate", "sync-cert-1")
