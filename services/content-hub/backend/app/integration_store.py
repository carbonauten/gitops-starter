from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import IntegrationConnection

INTEGRATION_SALT = "content-hub-integration-token"
PROVIDERS = ("microsoft", "notion")


def _serializer(settings: Settings | None = None) -> URLSafeSerializer:
    settings = settings or get_settings()
    return URLSafeSerializer(settings.session_secret, salt=INTEGRATION_SALT)


def encrypt_secret(value: str, settings: Settings | None = None) -> str:
    return _serializer(settings).dumps(value)


def decrypt_secret(value: str, settings: Settings | None = None) -> str:
    try:
        return _serializer(settings).loads(value)
    except BadSignature:
        return ""


def get_integration(db: Session, provider: str) -> IntegrationConnection | None:
    if provider not in PROVIDERS:
        return None
    return db.get(IntegrationConnection, provider)


def integration_status(db: Session, provider: str) -> dict[str, Any]:
    row = get_integration(db, provider)
    if not row or not row.access_token_enc:
        return {"connected": False, "account": "", "connected_at": None}
    return {
        "connected": True,
        "account": row.account_label,
        "connected_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def save_integration(
    db: Session,
    *,
    provider: str,
    access_token: str,
    refresh_token: str = "",
    expires_at: datetime | None = None,
    account_label: str = "",
    connected_by_id: str = "",
    connected_by_name: str = "",
) -> IntegrationConnection:
    row = get_integration(db, provider)
    if not row:
        row = IntegrationConnection(provider=provider)
        db.add(row)
    row.access_token_enc = encrypt_secret(access_token)
    row.refresh_token_enc = encrypt_secret(refresh_token) if refresh_token else ""
    row.expires_at = expires_at
    row.account_label = account_label
    row.connected_by_id = connected_by_id
    row.connected_by_name = connected_by_name
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def delete_integration(db: Session, provider: str) -> None:
    row = get_integration(db, provider)
    if row:
        db.delete(row)
        db.commit()


def read_access_token(row: IntegrationConnection) -> str:
    return decrypt_secret(row.access_token_enc)


def read_refresh_token(row: IntegrationConnection) -> str:
    return decrypt_secret(row.refresh_token_enc)
