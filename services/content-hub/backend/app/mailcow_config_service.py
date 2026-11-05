from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import PlatformMailcowSettings
from .user_integration_store import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class MailcowCredentials:
    api_url: str
    api_key: str
    default_domain: str
    source: str  # env | stored | none

    @property
    def configured(self) -> bool:
        return bool(self.api_url and self.api_key)


def _env_credentials() -> MailcowCredentials:
    settings = get_settings()
    return MailcowCredentials(
        api_url=settings.mailcow_api_url.strip().rstrip("/"),
        api_key=settings.mailcow_api_key.strip(),
        default_domain=settings.mailcow_default_domain.strip(),
        source="env" if settings.mailcow_env_configured else "none",
    )


def _stored_row(db: Session) -> PlatformMailcowSettings | None:
    return db.get(PlatformMailcowSettings, "default")


def _stored_credentials(db: Session) -> MailcowCredentials:
    row = _stored_row(db)
    if not row:
        return MailcowCredentials("", "", "", "none")
    key = decrypt_secret(row.api_key_enc or "")
    url = (row.api_url or "").strip().rstrip("/")
    if url and key:
        return MailcowCredentials(url, key, (row.default_domain or "").strip(), "stored")
    return MailcowCredentials(url, key, (row.default_domain or "").strip(), "none")


def resolve_mailcow_credentials(db: Session | None = None) -> MailcowCredentials:
    """Prefer Railway/env MAILCOW_*; fall back to IT-Master stored config."""
    env = _env_credentials()
    if env.configured:
        return env
    if db is None:
        return env
    stored = _stored_credentials(db)
    if stored.configured:
        return stored
    return env


def mailcow_status(db: Session) -> dict[str, Any]:
    creds = resolve_mailcow_credentials(db)
    row = _stored_row(db)
    return {
        "configured": creds.configured,
        "source": creds.source if creds.configured else "none",
        "api_url": creds.api_url if creds.configured else "",
        "default_domain": creds.default_domain,
        "stored_configured": _stored_credentials(db).configured,
        "env_configured": _env_credentials().configured,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by_name": (row.updated_by_name if row else "") or "",
    }


def save_mailcow_config(
    db: Session,
    *,
    api_url: str,
    api_key: str,
    default_domain: str,
    actor: dict[str, Any],
) -> dict[str, Any]:
    url = (api_url or "").strip().rstrip("/")
    key = (api_key or "").strip()
    domain = (default_domain or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="validation")

    row = _stored_row(db)
    if not row:
        row = PlatformMailcowSettings(id="default")
        db.add(row)

    row.api_url = url
    row.default_domain = domain
    if key:
        row.api_key_enc = encrypt_secret(key)
    elif not decrypt_secret(row.api_key_enc or ""):
        raise HTTPException(status_code=400, detail="validation")

    row.updated_by_id = str(actor.get("id") or actor.get("db_id") or "")
    row.updated_by_name = str(actor.get("name") or "")
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return mailcow_status(db)


def clear_stored_mailcow_config(db: Session) -> dict[str, Any]:
    row = _stored_row(db)
    if row:
        db.delete(row)
        db.commit()
    return mailcow_status(db)
