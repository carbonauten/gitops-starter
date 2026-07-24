from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import FileAsset
from .graph_client import get_app_access_token
from .graph_files_service import GRAPH_BASE, _resolve_sharepoint_drive_id
from .outlook_service import get_outlook_access_token

logger = logging.getLogger(__name__)

PREVIEW_SALT = "content-hub-office-preview"
PREVIEW_TTL_SECONDS = 600
OFFICE_EXTENSIONS = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}
SourceType = Literal["platform", "sharepoint", "onedrive"]


def _preview_serializer(settings: Settings | None = None) -> URLSafeTimedSerializer:
    settings = settings or get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=PREVIEW_SALT)


def mint_preview_token(file_id: str, user_id: str = "", settings: Settings | None = None) -> str:
    return _preview_serializer(settings).dumps({"file_id": file_id, "user_id": user_id})


def parse_preview_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    try:
        payload = _preview_serializer(settings).loads(token, max_age=PREVIEW_TTL_SECONDS)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail="preview_token_expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="preview_token_invalid") from exc
    if not isinstance(payload, dict) or not payload.get("file_id"):
        raise HTTPException(status_code=401, detail="preview_token_invalid")
    return payload


def is_office_filename(name: str) -> bool:
    lower = (name or "").lower()
    return any(lower.endswith(ext) for ext in OFFICE_EXTENSIONS)


def _public_origin(settings: Settings) -> str:
    return (settings.effective_public_origin or "http://localhost:8080").rstrip("/")


def office_viewer_embed_url(file_url: str) -> str:
    return f"https://view.officeapps.live.com/op/embed.aspx?src={quote(file_url, safe='')}"


async def _graph_post_json(path: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
        if response.status_code not in {200, 201}:
            logger.warning("Graph createLink failed %s: %s", path, response.text)
            raise HTTPException(status_code=502, detail="office_embed_failed")
        return response.json()


async def _graph_get_json(path: str, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            logger.error("Graph item fetch failed %s: %s", path, response.text)
            raise HTTPException(status_code=502, detail="graph_files_failed")
        return response.json()


async def _create_embed_link(token: str, item_create_link_path: str) -> str:
    for scope in ("organization", "anonymous"):
        try:
            payload = await _graph_post_json(
                item_create_link_path,
                token,
                {"type": "embed", "scope": scope},
            )
            link = payload.get("link") or {}
            web_url = link.get("webUrl") or ""
            if web_url:
                return web_url
        except HTTPException:
            continue
    return ""


async def _session_from_graph_item(
    *,
    token: str,
    item_path: str,
    create_link_path: str,
    source: SourceType,
) -> dict[str, Any]:
    item = await _graph_get_json(item_path, token)
    name = item.get("name") or "document"
    edit_url = item.get("webUrl") or ""
    embed_url = await _create_embed_link(token, create_link_path)
    if not embed_url and edit_url:
        # Fallback: some tenants block embed links; still expose edit URL.
        embed_url = ""
    return {
        "source": source,
        "item_id": item.get("id") or "",
        "name": name,
        "embed_url": embed_url,
        "edit_url": edit_url,
        "can_edit": bool(edit_url),
        "mock": False,
        "expires_at": None,
    }


async def create_onedrive_office_session(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not item_id or item_id == "root":
        raise HTTPException(status_code=400, detail="validation")

    try:
        token = await get_outlook_access_token(db, user_id=user_id)
    except HTTPException:
        token = None

    if not token:
        # Mock / not connected: allow opening panel with external Office link only.
        return {
            "source": "onedrive",
            "item_id": item_id,
            "name": item_id,
            "embed_url": "",
            "edit_url": "https://www.office.com",
            "can_edit": True,
            "mock": True,
            "expires_at": None,
        }

    return await _session_from_graph_item(
        token=token,
        item_path=f"/me/drive/items/{item_id}",
        create_link_path=f"/me/drive/items/{item_id}/createLink",
        source="onedrive",
    )


async def create_sharepoint_office_session(
    *,
    item_id: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not item_id or item_id == "root":
        raise HTTPException(status_code=400, detail="validation")

    if settings.files_browse_mock_mode or not settings.sharepoint_configured:
        return {
            "source": "sharepoint",
            "item_id": item_id,
            "name": item_id,
            "embed_url": "",
            "edit_url": "https://www.office.com",
            "can_edit": True,
            "mock": True,
            "expires_at": None,
        }

    token = await get_app_access_token(settings)
    drive_id = await _resolve_sharepoint_drive_id(settings)
    return await _session_from_graph_item(
        token=token,
        item_path=f"/drives/{drive_id}/items/{item_id}",
        create_link_path=f"/drives/{drive_id}/items/{item_id}/createLink",
        source="sharepoint",
    )


def create_platform_office_session(
    db: Session,
    *,
    file_id: str,
    user_id: str = "",
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    if not is_office_filename(file_asset.original_name):
        raise HTTPException(status_code=400, detail="not_office_document")

    token = mint_preview_token(file_id, user_id=user_id, settings=settings)
    preview_url = f"{_public_origin(settings)}/api/files/public-preview?token={quote(token, safe='')}"
    expires = datetime.now(timezone.utc).timestamp() + PREVIEW_TTL_SECONDS
    return {
        "source": "platform",
        "item_id": file_id,
        "name": file_asset.original_name,
        "embed_url": office_viewer_embed_url(preview_url),
        "edit_url": "",
        "can_edit": False,
        "mock": False,
        "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
        "preview_url": preview_url,
    }


async def create_office_session(
    db: Session,
    *,
    source: SourceType,
    item_id: str,
    user: dict[str, Any],
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    user_id = user.get("db_id") or ""
    if source == "platform":
        return create_platform_office_session(db, file_id=item_id, user_id=user_id, settings=settings)
    if source == "sharepoint":
        return await create_sharepoint_office_session(item_id=item_id, settings=settings)
    return await create_onedrive_office_session(db, user_id=user_id, item_id=item_id, settings=settings)
