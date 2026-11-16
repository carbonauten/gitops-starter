from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .database import PlatformStratoSettings
from .user_integration_store import decrypt_secret, encrypt_secret


def _parse_domains(raw: str) -> list[str]:
    """Splits on commas/newlines/whitespace, lowercases, dedupes, drops junk.

    Strato has no API to list the domains on an account, and the browser
    automation in strato_automation_service.py is explicitly untested
    against a live account - so this is a manually maintained hint for the
    domain picker, not anything scraped live."""
    pieces = re.split(r"[,\n\r\t ]+", raw or "")
    seen: dict[str, None] = {}
    for piece in pieces:
        domain = piece.strip().lower()
        if domain and domain not in seen:
            seen[domain] = None
    return list(seen)


@dataclass(frozen=True)
class StratoCredentials:
    customer_number: str
    password: str
    domains: list[str] = field(default_factory=list)

    @property
    def configured(self) -> bool:
        return bool(self.customer_number and self.password)


def _stored_row(db: Session) -> PlatformStratoSettings | None:
    return db.get(PlatformStratoSettings, "default")


def resolve_strato_credentials(db: Session) -> StratoCredentials:
    row = _stored_row(db)
    if not row:
        return StratoCredentials("", "")
    return StratoCredentials(
        row.customer_number or "",
        decrypt_secret(row.password_enc or ""),
        _parse_domains(row.domains or ""),
    )


def strato_status(db: Session) -> dict[str, Any]:
    row = _stored_row(db)
    creds = resolve_strato_credentials(db)
    return {
        "configured": creds.configured,
        "customer_number": creds.customer_number,
        "domains": creds.domains,
        "domains_raw": (row.domains if row else "") or "",
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by_name": (row.updated_by_name if row else "") or "",
    }


def save_strato_config(
    db: Session,
    *,
    customer_number: str,
    password: str,
    actor: dict[str, Any],
) -> dict[str, Any]:
    number = (customer_number or "").strip()
    if not number:
        raise HTTPException(status_code=400, detail="validation")

    row = _stored_row(db)
    if not row:
        row = PlatformStratoSettings(id="default")
        db.add(row)

    row.customer_number = number
    if password:
        row.password_enc = encrypt_secret(password)
    elif not decrypt_secret(row.password_enc or ""):
        raise HTTPException(status_code=400, detail="validation")

    row.updated_by_id = str(actor.get("id") or actor.get("db_id") or "")
    row.updated_by_name = str(actor.get("name") or "")
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return strato_status(db)


def save_strato_domains(db: Session, *, domains: str, actor: dict[str, Any]) -> dict[str, Any]:
    row = _stored_row(db)
    if not row:
        raise HTTPException(status_code=400, detail="strato_automation_not_configured")

    row.domains = domains or ""
    row.updated_by_id = str(actor.get("id") or actor.get("db_id") or "")
    row.updated_by_name = str(actor.get("name") or "")
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return strato_status(db)


def clear_stored_strato_config(db: Session) -> dict[str, Any]:
    row = _stored_row(db)
    if row:
        db.delete(row)
        db.commit()
    return strato_status(db)
