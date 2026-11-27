from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import FileAsset
from .storage import read_upload

logger = logging.getLogger(__name__)

# Self-hosted Documenso (https://documenso.com, AGPL, services/documenso) -
# lets files stored in the platform file manager be signed in-app instead of
# juggling a separate external tool. This is a thin httpx client around
# Documenso's "v2 envelope" REST API; see services/documenso/README.md for
# the Railway setup this needs.
#
# KNOWN UNVERIFIED AREAS (no live Documenso instance was available while
# writing this - see the PR description for the full list):
#   - download_signed_pdf() below: the exact endpoint for fetching a
#     completed envelope's signed PDF bytes is not clearly documented. Best
#     guess per Documenso's migration-to-envelopes docs: the item is fetched
#     via GET /api/v2/envelope/{id} (envelopeItems[].id), then downloaded via
#     GET /api/v2/envelope/item/{envelopeItemId}/download. MUST be verified
#     against a real deployed instance.
#   - Embedded (iframe) signing may be gated behind Documenso's paid "Teams"
#     plan even for self-hosted instances (undocumented either way) - see
#     DocumentSignPanel.tsx's window.open() fallback.
#   - The webhook payload shape (`event` / `data.id`) below is inferred from
#     Documenso's general webhook conventions, not pinned to an exact schema.

DOCUMENSO_API_PREFIX = "/api/v2"


def _documenso_base_url() -> str:
    return get_settings().documenso_base_url.strip().rstrip("/")


def documenso_configured() -> bool:
    settings = get_settings()
    return bool(settings.documenso_base_url.strip() and settings.documenso_api_key.strip())


def _headers() -> dict[str, str]:
    # Documenso-specific: the v2 API takes the raw API key in the
    # Authorization header, with NO "Bearer" prefix.
    return {"Authorization": get_settings().documenso_api_key.strip()}


def read_file_asset_bytes(file_asset: FileAsset) -> bytes:
    if file_asset.storage_path == "db://postgres":
        return file_asset.content or b""
    return read_upload(file_asset.storage_path)


async def create_envelope(
    *,
    pdf_bytes: bytes,
    filename: str,
    title: str,
    signer_email: str,
    signer_name: str,
) -> dict[str, Any]:
    """POST /api/v2/envelope/create - multipart: a `payload` JSON part
    describing the envelope/recipients, plus the PDF itself. Returns the
    created envelope, e.g. {"id": "envelope_..."}."""
    base = _documenso_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="documenso_not_configured")

    payload = {
        "type": "DOCUMENT",
        "title": title,
        "recipients": [
            {
                "email": signer_email,
                "name": signer_name or signer_email,
                "role": "SIGNER",
                # Best-guess default signature field placement (bottom-left
                # of page 1, normalized percentages) - Documenso's exact
                # field-position schema should be re-checked against a real
                # instance; adjust once embedded signing is verified.
                "fields": [
                    {
                        "type": "SIGNATURE",
                        "page": 1,
                        "positionX": 10,
                        "positionY": 85,
                        "width": 25,
                        "height": 8,
                    }
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base}{DOCUMENSO_API_PREFIX}/envelope/create",
            headers=_headers(),
            data={"payload": json.dumps(payload)},
            files={"files": (filename, pdf_bytes, "application/pdf")},
        )
        if response.status_code not in (200, 201):
            logger.warning("Documenso envelope create failed: %s", response.text)
            raise HTTPException(status_code=502, detail="documenso_create_failed")
        return response.json()


async def distribute_envelope(envelope_id: str) -> dict[str, Any]:
    """POST /api/v2/envelope/distribute - sends the envelope out and returns
    per-recipient signing tokens/URLs, e.g. {"recipients": [{"token": "...",
    "signingUrl": "..."}]}."""
    base = _documenso_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="documenso_not_configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{base}{DOCUMENSO_API_PREFIX}/envelope/distribute",
            headers=_headers(),
            json={"envelopeId": envelope_id},
        )
        if response.status_code not in (200, 201):
            logger.warning("Documenso envelope distribute failed: %s", response.text)
            raise HTTPException(status_code=502, detail="documenso_distribute_failed")
        return response.json()


async def get_envelope_status(envelope_id: str) -> dict[str, Any]:
    """GET /api/v2/envelope/{id} - the envelope's current status plus its
    envelopeItems (needed by download_signed_pdf below)."""
    base = _documenso_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="documenso_not_configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{base}{DOCUMENSO_API_PREFIX}/envelope/{envelope_id}",
            headers=_headers(),
        )
        if response.status_code != 200:
            logger.warning("Documenso envelope status fetch failed: %s", response.text)
            raise HTTPException(status_code=502, detail="documenso_status_failed")
        return response.json()


async def download_signed_pdf(envelope_id: str) -> bytes:
    """BEST GUESS, UNVERIFIED (see module docstring): fetches the completed
    envelope's signed PDF bytes.

    Documenso's public docs document a deprecated v1 route
    (`GET /api/v2/document/{documentId}/download`) that migrated to
    `GET /api/v2/envelope/item/{envelopeItemId}/download` under the v2
    "envelope" model, but the exact response shape for that endpoint isn't
    spelled out anywhere findable. This handles both plausible shapes: a
    direct binary PDF response, or a JSON body carrying a `url`/`downloadUrl`
    to fetch separately. MUST be checked against a real deployed instance
    before relying on this in production.
    """
    base = _documenso_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="documenso_not_configured")

    status = await get_envelope_status(envelope_id)
    envelope_items = status.get("envelopeItems") or []
    if not envelope_items:
        raise HTTPException(status_code=502, detail="documenso_no_envelope_items")
    item_id = envelope_items[0].get("id")
    if not item_id:
        raise HTTPException(status_code=502, detail="documenso_no_envelope_item_id")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base}{DOCUMENSO_API_PREFIX}/envelope/item/{item_id}/download",
            headers=_headers(),
        )
        if response.status_code != 200:
            logger.warning("Documenso signed PDF download failed: %s", response.text)
            raise HTTPException(status_code=502, detail="documenso_download_failed")

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            body = response.json()
            download_url = body.get("url") or body.get("downloadUrl")
            if not download_url:
                raise HTTPException(status_code=502, detail="documenso_download_url_missing")
            file_response = await client.get(download_url)
            if file_response.status_code != 200:
                raise HTTPException(status_code=502, detail="documenso_download_failed")
            return file_response.content

        return response.content


def signed_file_name(original_name: str) -> str:
    path = Path(original_name or "document.pdf")
    stem = path.stem or "document"
    return f"{stem} (signed).pdf"
