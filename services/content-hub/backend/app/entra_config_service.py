from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import PlatformEntraSettings
from .user_integration_store import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class EntraCredentials:
    tenant_id: str
    client_id: str
    client_secret: str
    source: str  # env | stored | none

    @property
    def configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)


def _env_credentials() -> EntraCredentials:
    settings = get_settings()
    return EntraCredentials(
        tenant_id=settings.azure_tenant_id.strip(),
        client_id=settings.azure_client_id.strip(),
        client_secret=settings.azure_client_secret.strip(),
        source="env" if settings.entra_configured else "none",
    )


def _stored_row(db: Session) -> PlatformEntraSettings | None:
    return db.get(PlatformEntraSettings, "default")


def _stored_credentials(db: Session) -> EntraCredentials:
    row = _stored_row(db)
    if not row:
        return EntraCredentials("", "", "", "none")
    secret = decrypt_secret(row.client_secret_enc or "")
    tenant = (row.tenant_id or "").strip()
    client_id = (row.client_id or "").strip()
    if tenant and client_id and secret:
        return EntraCredentials(tenant, client_id, secret, "stored")
    return EntraCredentials(tenant, client_id, secret, "none")


def resolve_entra_credentials(db: Session | None = None) -> EntraCredentials:
    """Prefer Railway/env AZURE_*; fall back to IT-Master stored app registration."""
    env = _env_credentials()
    if env.configured:
        return env
    if db is None:
        return env
    stored = _stored_credentials(db)
    if stored.configured:
        return stored
    return env


def entra_status(db: Session) -> dict[str, Any]:
    creds = resolve_entra_credentials(db)
    row = _stored_row(db)
    origin = get_settings().effective_public_origin or "https://app.carbonauten.com"
    redirect_uris = [
        f"{origin}/api/auth/callback",
        f"{origin}/api/integrations/microsoft/callback",
        f"{origin}/api/integrations/outlook/callback",
    ]
    admin_consent_url = ""
    if creds.configured:
        from urllib.parse import urlencode

        admin_consent_url = (
            f"https://login.microsoftonline.com/{creds.tenant_id}/v2.0/adminconsent?"
            f"{urlencode({'client_id': creds.client_id, 'redirect_uri': f'{origin}/mail', 'state': 'admin_consent'})}"
        )
    return {
        "oauth_available": creds.configured,
        "source": creds.source if creds.configured else "none",
        "tenant_id": creds.tenant_id if creds.configured else "",
        "client_id": creds.client_id if creds.configured else "",
        "has_client_secret": bool(creds.client_secret) if creds.configured else False,
        "stored_configured": _stored_credentials(db).configured,
        "env_configured": _env_credentials().configured,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by_name": (row.updated_by_name if row else "") or "",
        "redirect_uris": redirect_uris,
        "admin_consent_url": admin_consent_url,
        "delegated_scopes": [
            "User.Read",
            "Mail.Read",
            "Calendars.Read",
            "Files.Read",
            "offline_access",
        ],
    }


def save_entra_credentials(
    db: Session,
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    actor: dict[str, Any],
) -> dict[str, Any]:
    tenant = (tenant_id or "").strip()
    client = (client_id or "").strip()
    secret = (client_secret or "").strip()
    if not tenant or not client:
        raise HTTPException(status_code=400, detail="validation")

    row = _stored_row(db)
    if not row:
        row = PlatformEntraSettings(id="default")
        db.add(row)

    row.tenant_id = tenant
    row.client_id = client
    if secret:
        row.client_secret_enc = encrypt_secret(secret)
    elif not decrypt_secret(row.client_secret_enc or ""):
        raise HTTPException(status_code=400, detail="validation")

    row.updated_by_id = str(actor.get("id") or actor.get("db_id") or "")
    row.updated_by_name = str(actor.get("name") or "")
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return entra_status(db)


def clear_stored_entra_credentials(db: Session) -> dict[str, Any]:
    row = _stored_row(db)
    if row:
        db.delete(row)
        db.commit()
    return entra_status(db)
