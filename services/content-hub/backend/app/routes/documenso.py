from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import DocumentSignature, FileAsset, get_db
from ..dependencies import get_current_user, require_editor
from ..documenso_service import (
    create_envelope,
    distribute_envelope,
    documenso_configured,
    download_signed_pdf,
    read_file_asset_bytes,
    signed_file_name,
)
from ..embedding_service import queue_reembed
from ..storage import save_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documenso"])


def _get_file_or_404(db: Session, file_id: str) -> FileAsset:
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    return file_asset


def _latest_signature(db: Session, file_id: str) -> DocumentSignature | None:
    return db.scalar(
        select(DocumentSignature)
        .where(DocumentSignature.file_asset_id == file_id)
        .order_by(DocumentSignature.created_at.desc())
    )


def _signature_to_dict(signature: DocumentSignature) -> dict[str, Any]:
    return {
        "id": signature.id,
        "file_asset_id": signature.file_asset_id,
        "signed_file_asset_id": signature.signed_file_asset_id,
        "status": signature.status,
        "signer_email": signature.signer_email,
        "signer_name": signature.signer_name,
        "created_at": signature.created_at.isoformat() if signature.created_at else None,
        "completed_at": signature.completed_at.isoformat() if signature.completed_at else None,
    }


@router.post("/api/files/{file_id}/sign", status_code=201)
async def sign_file(
    file_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict[str, Any]:
    if not documenso_configured():
        raise HTTPException(status_code=400, detail="documenso_not_configured")

    file_asset = _get_file_or_404(db, file_id)
    content = read_file_asset_bytes(file_asset)
    signer_email = user.get("email", "")
    signer_name = user.get("name", "") or signer_email
    if not signer_email:
        raise HTTPException(status_code=400, detail="validation")

    envelope = await create_envelope(
        pdf_bytes=content,
        filename=file_asset.original_name,
        title=file_asset.original_name,
        signer_email=signer_email,
        signer_name=signer_name,
    )
    envelope_id = envelope.get("id")
    if not envelope_id:
        raise HTTPException(status_code=502, detail="documenso_create_failed")

    distribution = await distribute_envelope(envelope_id)
    recipients = distribution.get("recipients") or []
    token = recipients[0].get("token") if recipients else None
    external_signing_url = recipients[0].get("signingUrl") if recipients else None

    signature = DocumentSignature(
        file_asset_id=file_asset.id,
        documenso_envelope_id=envelope_id,
        status="pending",
        signer_email=signer_email,
        signer_name=signer_name,
        signing_token=token or "",
    )
    db.add(signature)
    db.commit()
    db.refresh(signature)

    settings = get_settings()
    embed_signing_url = (
        f"{settings.documenso_base_url.strip().rstrip('/')}/embed/sign/{token}" if token else None
    )

    return {
        "signature": _signature_to_dict(signature),
        "signing_url": embed_signing_url,
        "external_signing_url": external_signing_url,
    }


@router.get("/api/files/{file_id}/sign/status")
def file_sign_status(
    file_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _get_file_or_404(db, file_id)
    signature = _latest_signature(db, file_id)
    if not signature:
        return {"signature": None}
    return {"signature": _signature_to_dict(signature)}


@router.post("/api/documenso/webhook")
async def documenso_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Receives Documenso's completion webhook and saves the signed PDF back
    as a new FileAsset. Auth is a shared secret header, not a session cookie
    - Documenso's SERVER calls this directly, like Collabora calls the WOPI
    endpoints in wopi.py.

    NOTE: the exact webhook payload shape below (`event` / `data.id`) is a
    best guess, not pinned to Documenso's real schema - verify once a live
    instance can actually be configured to send webhooks here. See the PR
    description.
    """
    settings = get_settings()
    expected_secret = settings.documenso_webhook_secret.strip()
    if not expected_secret:
        raise HTTPException(status_code=400, detail="documenso_webhook_not_configured")
    provided_secret = request.headers.get("X-Documenso-Secret", "")
    if provided_secret != expected_secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    body = await request.json()
    event = body.get("event") or body.get("type")
    data = body.get("data") or {}
    envelope_id = data.get("id") or data.get("envelopeId") or body.get("envelopeId")
    if not envelope_id:
        raise HTTPException(status_code=400, detail="validation")

    signature = db.scalar(
        select(DocumentSignature).where(DocumentSignature.documenso_envelope_id == envelope_id)
    )
    if not signature:
        logger.warning("Documenso webhook for unknown envelope %s", envelope_id)
        return {"ok": True}

    if event in ("DOCUMENT_COMPLETED", "ENVELOPE_COMPLETED"):
        await _store_signed_pdf(db, signature, background_tasks=background_tasks)
    elif event in ("DOCUMENT_REJECTED", "ENVELOPE_REJECTED"):
        signature.status = "rejected"
        db.add(signature)
        db.commit()
    elif event in ("DOCUMENT_CANCELLED", "ENVELOPE_CANCELLED", "DOCUMENT_VOIDED"):
        signature.status = "cancelled"
        db.add(signature)
        db.commit()

    return {"ok": True}


async def _store_signed_pdf(
    db: Session,
    signature: DocumentSignature,
    *,
    background_tasks: BackgroundTasks,
) -> None:
    file_asset = db.get(FileAsset, signature.file_asset_id)
    if not file_asset:
        logger.warning("Documenso webhook: original file %s not found", signature.file_asset_id)
        signature.status = "completed"
        signature.completed_at = datetime.now(timezone.utc)
        db.add(signature)
        db.commit()
        return

    pdf_bytes = await download_signed_pdf(signature.documenso_envelope_id)
    original_name = signed_file_name(file_asset.original_name)
    stored_name, storage_path, _ = save_upload(pdf_bytes, original_name)

    signed_asset = FileAsset(
        original_name=original_name,
        stored_name=stored_name,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
        folder=file_asset.folder,
        folder_id=file_asset.folder_id,
        storage_path=storage_path,
        uploaded_by_id=file_asset.uploaded_by_id,
        uploaded_by_name=signature.signer_name or file_asset.uploaded_by_name,
    )
    db.add(signed_asset)
    signature.status = "completed"
    signature.completed_at = datetime.now(timezone.utc)
    db.add(signature)
    db.commit()
    db.refresh(signed_asset)
    signature.signed_file_asset_id = signed_asset.id
    db.add(signature)
    db.commit()

    queue_reembed(background_tasks, entity_type="file", entity_id=signed_asset.id)
