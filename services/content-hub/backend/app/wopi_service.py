from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import FileAsset
from .office_embed_service import is_office_filename
from .storage import overwrite_upload, read_upload

# Minimal WOPI host (https://learn.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/online/)
# for Collabora Online (services/collabora-code) to edit platform-stored
# FileAssets live. Auth is a single signed, short-lived access_token per
# editing session - Collabora's server calls these endpoints directly
# (never through the user's browser session), so there's no cookie auth
# here, only the token.

WOPI_SALT = "content-hub-wopi-token"
WOPI_TOKEN_TTL_SECONDS = 4 * 60 * 60  # one editing session
LOCK_TTL_SECONDS = 30 * 60  # WOPI convention: locks expire after ~30 min idle

# {file_id: (lock_id, expires_at)}. In-memory and per-process: fine with
# numReplicas = 1 (see railway.toml), but a redeploy mid-edit drops any
# outstanding lock - an accepted tradeoff for a first version, see
# services/collabora-code/README.md.
_locks: dict[str, tuple[str, datetime]] = {}


def _serializer(settings: Settings | None = None) -> URLSafeTimedSerializer:
    settings = settings or get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt=WOPI_SALT)


def mint_wopi_token(file_id: str, *, user_id: str, user_name: str, settings: Settings | None = None) -> str:
    return _serializer(settings).dumps({"file_id": file_id, "user_id": user_id, "user_name": user_name})


def parse_wopi_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    try:
        payload = _serializer(settings).loads(token, max_age=WOPI_TOKEN_TTL_SECONDS)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail="wopi_token_expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="wopi_token_invalid") from exc
    if not isinstance(payload, dict) or not payload.get("file_id"):
        raise HTTPException(status_code=401, detail="wopi_token_invalid")
    return payload


def collabora_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.collabora_url.strip())


def collabora_edit_url(
    file_asset: FileAsset,
    *,
    user_id: str,
    user_name: str,
    settings: Settings | None = None,
) -> str | None:
    settings = settings or get_settings()
    collabora_url = settings.collabora_url.strip()
    if not collabora_url or not is_office_filename(file_asset.original_name):
        return None

    token = mint_wopi_token(file_asset.id, user_id=user_id, user_name=user_name, settings=settings)
    wopi_src = f"{settings.effective_public_origin}/wopi/files/{file_asset.id}"
    # /browser/dist/cool.html is Collabora CODE's stable convenience alias
    # for "load the editor for whatever WOPISrc is given" - avoids having to
    # parse /hosting/discovery.xml for the right per-mimetype action URL.
    return (
        f"{collabora_url.rstrip('/')}/browser/dist/cool.html"
        f"?WOPISrc={quote(wopi_src, safe='')}&access_token={quote(token, safe='')}"
    )


def _get_file_or_404(db: Session, file_id: str) -> FileAsset:
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    return file_asset


def _read_content(file_asset: FileAsset) -> bytes:
    if file_asset.storage_path == "db://postgres":
        return file_asset.content or b""
    return read_upload(file_asset.storage_path)


def _write_content(db: Session, file_asset: FileAsset, content: bytes) -> None:
    if file_asset.storage_path == "db://postgres":
        file_asset.content = content
    else:
        overwrite_upload(file_asset.storage_path, content)
    file_asset.size_bytes = len(content)
    db.add(file_asset)
    db.commit()


def check_file_info(db: Session, *, file_id: str, token_payload: dict[str, Any]) -> dict[str, Any]:
    file_asset = _get_file_or_404(db, file_id)
    content = _read_content(file_asset)
    version = hashlib.md5(content).hexdigest()[:16]
    return {
        "BaseFileName": file_asset.original_name,
        "Size": len(content),
        "OwnerId": file_asset.uploaded_by_id,
        "UserId": token_payload.get("user_id") or "",
        "UserFriendlyName": token_payload.get("user_name") or "User",
        "UserCanWrite": True,
        "UserCanNotWriteRelative": True,
        "Version": version,
        "LastModifiedTime": file_asset.created_at.isoformat() if file_asset.created_at else None,
    }


def get_file_contents(db: Session, *, file_id: str) -> bytes:
    file_asset = _get_file_or_404(db, file_id)
    return _read_content(file_asset)


def _active_lock(file_id: str) -> str | None:
    entry = _locks.get(file_id)
    if not entry:
        return None
    lock_id, expires_at = entry
    if expires_at < datetime.now(timezone.utc):
        _locks.pop(file_id, None)
        return None
    return lock_id


def lock(file_id: str, *, new_lock: str) -> tuple[int, str]:
    """Returns (status_code, current_lock_id). 200 = locked/relocked, 409 = conflict."""
    existing = _active_lock(file_id)
    if existing and existing != new_lock:
        return 409, existing
    _locks[file_id] = (new_lock, datetime.now(timezone.utc) + timedelta(seconds=LOCK_TTL_SECONDS))
    return 200, new_lock


def get_lock(file_id: str) -> str:
    return _active_lock(file_id) or ""


def refresh_lock(file_id: str, *, expected_lock: str) -> tuple[int, str]:
    existing = _active_lock(file_id)
    if not existing:
        return 409, ""
    if existing != expected_lock:
        return 409, existing
    _locks[file_id] = (existing, datetime.now(timezone.utc) + timedelta(seconds=LOCK_TTL_SECONDS))
    return 200, existing


def unlock(file_id: str, *, expected_lock: str) -> tuple[int, str]:
    existing = _active_lock(file_id)
    if not existing:
        return 409, ""
    if existing != expected_lock:
        return 409, existing
    _locks.pop(file_id, None)
    return 200, ""


def put_file(db: Session, *, file_id: str, content: bytes, provided_lock: str) -> int:
    """Returns the HTTP status code to send back (200 ok, 409 lock conflict)."""
    existing = _active_lock(file_id)
    # No active lock and no lock header is fine (Collabora allows unlocked
    # single-shot saves for files nobody else is editing concurrently).
    if existing and existing != provided_lock:
        return 409
    file_asset = _get_file_or_404(db, file_id)
    _write_content(db, file_asset, content)
    return 200
