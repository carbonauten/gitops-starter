from io import BytesIO

import pytest

from app.documenso_service import documenso_configured, read_file_asset_bytes, signed_file_name


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_documenso_configured_false_by_default():
    assert documenso_configured() is False


def test_documenso_configured_requires_base_url_and_api_key(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DOCUMENSO_BASE_URL", "https://documenso.example.com")
    monkeypatch.setenv("DOCUMENSO_API_KEY", "")
    get_settings.cache_clear()
    assert documenso_configured() is False

    monkeypatch.setenv("DOCUMENSO_API_KEY", "api_test_key")
    get_settings.cache_clear()
    assert documenso_configured() is True
    get_settings.cache_clear()


def test_signed_file_name_appends_signed_suffix():
    assert signed_file_name("contract.pdf") == "contract (signed).pdf"
    assert signed_file_name("report.docx") == "report (signed).pdf"


def test_read_file_asset_bytes_from_local_storage(db_session):
    from app.database import FileAsset
    from app.storage import save_upload

    stored_name, storage_path, _ = save_upload(b"hello pdf", "doc.pdf")
    file_asset = FileAsset(
        original_name="doc.pdf",
        stored_name=stored_name,
        content_type="application/pdf",
        size_bytes=9,
        storage_path=storage_path,
        uploaded_by_id="user-1",
        uploaded_by_name="Mike",
    )
    db_session.add(file_asset)
    db_session.commit()
    db_session.refresh(file_asset)

    assert read_file_asset_bytes(file_asset) == b"hello pdf"


def test_sign_file_requires_documenso_configured(auth_client):
    payload = BytesIO(b"%PDF-1.4 fake pdf content")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("contract.pdf", payload, "application/pdf")},
        data={"folder": "compliance"},
    )
    file_id = upload.json()["file"]["id"]

    response = auth_client.post(f"/api/files/{file_id}/sign")
    assert response.status_code == 400
    assert response.json()["code"] == "documenso_not_configured"


def test_sign_file_creates_signature_and_returns_signing_url(auth_client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DOCUMENSO_BASE_URL", "https://documenso.example.com")
    monkeypatch.setenv("DOCUMENSO_API_KEY", "api_test_key")
    get_settings.cache_clear()

    async def fake_create_envelope(**kwargs):
        return {"id": "envelope_abc123"}

    async def fake_distribute_envelope(envelope_id):
        assert envelope_id == "envelope_abc123"
        return {
            "recipients": [
                {"token": "recipient-token-xyz", "signingUrl": "https://documenso.example.com/sign/recipient-token-xyz"}
            ]
        }

    monkeypatch.setattr("app.routes.documenso.create_envelope", fake_create_envelope)
    monkeypatch.setattr("app.routes.documenso.distribute_envelope", fake_distribute_envelope)

    payload = BytesIO(b"%PDF-1.4 fake pdf content")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("contract.pdf", payload, "application/pdf")},
        data={"folder": "compliance"},
    )
    file_id = upload.json()["file"]["id"]

    response = auth_client.post(f"/api/files/{file_id}/sign")
    assert response.status_code == 201
    body = response.json()
    assert body["signature"]["status"] == "pending"
    assert body["signature"]["file_asset_id"] == file_id
    assert body["signing_url"] == "https://documenso.example.com/embed/sign/recipient-token-xyz"
    assert body["external_signing_url"] == "https://documenso.example.com/sign/recipient-token-xyz"

    status_response = auth_client.get(f"/api/files/{file_id}/sign/status")
    assert status_response.status_code == 200
    assert status_response.json()["signature"]["status"] == "pending"

    get_settings.cache_clear()


def test_sign_status_returns_none_when_never_signed(auth_client):
    payload = BytesIO(b"%PDF-1.4 fake pdf content")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("untouched.pdf", payload, "application/pdf")},
        data={"folder": "compliance"},
    )
    file_id = upload.json()["file"]["id"]

    response = auth_client.get(f"/api/files/{file_id}/sign/status")
    assert response.status_code == 200
    assert response.json() == {"signature": None}


def test_webhook_rejects_without_configured_secret(client):
    response = client.post(
        "/api/documenso/webhook",
        json={"event": "DOCUMENT_COMPLETED", "data": {"id": "envelope_abc123"}},
    )
    assert response.status_code == 400


def test_webhook_rejects_wrong_secret(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("DOCUMENSO_WEBHOOK_SECRET", "correct-secret")
    get_settings.cache_clear()

    response = client.post(
        "/api/documenso/webhook",
        json={"event": "DOCUMENT_COMPLETED", "data": {"id": "envelope_abc123"}},
        headers={"X-Documenso-Secret": "wrong-secret"},
    )
    assert response.status_code == 401
    get_settings.cache_clear()


def test_webhook_document_completed_stores_signed_pdf_as_new_file(auth_client, monkeypatch):
    from app.config import get_settings
    from app.database import DocumentSignature, FileAsset, _SessionLocal

    monkeypatch.setenv("DOCUMENSO_BASE_URL", "https://documenso.example.com")
    monkeypatch.setenv("DOCUMENSO_API_KEY", "api_test_key")
    monkeypatch.setenv("DOCUMENSO_WEBHOOK_SECRET", "whsec_test")
    get_settings.cache_clear()

    payload = BytesIO(b"%PDF-1.4 original contract")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("contract.pdf", payload, "application/pdf")},
        data={"folder": "compliance"},
    )
    file_id = upload.json()["file"]["id"]

    db = _SessionLocal()
    try:
        signature = DocumentSignature(
            file_asset_id=file_id,
            documenso_envelope_id="envelope_abc123",
            status="pending",
            signer_email="demo@example.com",
            signer_name="Demo User",
            signing_token="recipient-token-xyz",
        )
        db.add(signature)
        db.commit()
    finally:
        db.close()

    async def fake_download_signed_pdf(envelope_id):
        assert envelope_id == "envelope_abc123"
        return b"%PDF-1.4 signed contract bytes"

    monkeypatch.setattr("app.routes.documenso.download_signed_pdf", fake_download_signed_pdf)

    response = auth_client.post(
        "/api/documenso/webhook",
        json={"event": "DOCUMENT_COMPLETED", "data": {"id": "envelope_abc123"}},
        headers={"X-Documenso-Secret": "whsec_test"},
    )
    assert response.status_code == 200

    status_response = auth_client.get(f"/api/files/{file_id}/sign/status")
    signature_payload = status_response.json()["signature"]
    assert signature_payload["status"] == "completed"
    assert signature_payload["signed_file_asset_id"]

    db = _SessionLocal()
    try:
        signed_asset = db.get(FileAsset, signature_payload["signed_file_asset_id"])
        assert signed_asset is not None
        assert signed_asset.original_name == "contract (signed).pdf"
        assert signed_asset.folder == db.get(FileAsset, file_id).folder
    finally:
        db.close()

    get_settings.cache_clear()
