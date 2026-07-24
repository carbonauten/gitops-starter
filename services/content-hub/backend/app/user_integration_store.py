from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import UserIntegration

USER_INTEGRATION_SALT = "content-hub-user-integration-token"
USER_PROVIDERS = ("outlook",)


def _serializer(settings: Settings | None = None) -> URLSafeSerializer:
    settings = settings or get_settings()
    return URLSafeSerializer(settings.session_secret, salt=USER_INTEGRATION_SALT)


def encrypt_secret(value: str, settings: Settings | None = None) -> str:
    return _serializer(settings).dumps(value)


def decrypt_secret(value: str, settings: Settings | None = None) -> str:
    try:
        return _serializer(settings).loads(value)
    except BadSignature:
        return ""


def get_user_integration(db: Session, *, user_id: str, provider: str) -> UserIntegration | None:
    if provider not in USER_PROVIDERS or not user_id:
        return None
    return db.scalar(
        select(UserIntegration).where(
            UserIntegration.user_id == user_id,
            UserIntegration.provider == provider,
        )
    )


def user_integration_status(db: Session, *, user_id: str, provider: str) -> dict[str, Any]:
    row = get_user_integration(db, user_id=user_id, provider=provider)
    if not row or not row.access_token_enc:
        return {
            "connected": False,
            "account": "",
            "connected_at": None,
            "calendar_enabled": False,
            "mail_enabled": False,
        }
    return {
        "connected": True,
        "account": row.account_label,
        "connected_at": row.updated_at.isoformat() if row.updated_at else None,
        "calendar_enabled": bool(row.calendar_enabled),
        "mail_enabled": bool(row.mail_enabled),
    }


def save_user_integration(
    db: Session,
    *,
    user_id: str,
    provider: str,
    access_token: str,
    refresh_token: str = "",
    expires_at: datetime | None = None,
    account_label: str = "",
    calendar_enabled: bool = True,
    mail_enabled: bool = True,
) -> UserIntegration:
    row = get_user_integration(db, user_id=user_id, provider=provider)
    if not row:
        row = UserIntegration(id=str(uuid4()), user_id=user_id, provider=provider)
        db.add(row)
    row.access_token_enc = encrypt_secret(access_token)
    row.refresh_token_enc = encrypt_secret(refresh_token) if refresh_token else ""
    row.expires_at = expires_at
    row.account_label = account_label
    row.calendar_enabled = calendar_enabled
    row.mail_enabled = mail_enabled
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def delete_user_integration(db: Session, *, user_id: str, provider: str) -> None:
    row = get_user_integration(db, user_id=user_id, provider=provider)
    if row:
        db.delete(row)
        db.commit()


def read_user_access_token(row: UserIntegration) -> str:
    return decrypt_secret(row.access_token_enc)


def read_user_refresh_token(row: UserIntegration) -> str:
    return decrypt_secret(row.refresh_token_enc)
