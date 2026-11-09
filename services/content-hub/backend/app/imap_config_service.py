from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import ImapMailAccount
from .user_integration_store import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class ImapCredentials:
    id: str
    label: str
    host: str
    port: int
    use_ssl: bool
    username: str
    password: str
    folder: str


def _account_summary(row: ImapMailAccount) -> dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "host": row.host,
        "port": row.port,
        "use_ssl": row.use_ssl,
        "username": row.username,
        "folder": row.folder,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_imap_accounts(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(ImapMailAccount).order_by(ImapMailAccount.label)).all()
    return [_account_summary(row) for row in rows]


def get_imap_account_row(db: Session, account_id: str) -> ImapMailAccount:
    row = db.get(ImapMailAccount, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return row


def get_imap_credentials(db: Session, account_id: str) -> ImapCredentials:
    row = get_imap_account_row(db, account_id)
    return ImapCredentials(
        id=row.id,
        label=row.label,
        host=row.host,
        port=row.port,
        use_ssl=row.use_ssl,
        username=row.username,
        password=decrypt_secret(row.password_enc or ""),
        folder=row.folder or "INBOX",
    )


def create_imap_account(
    db: Session,
    *,
    label: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    password: str,
    folder: str,
    actor: dict[str, Any],
) -> dict[str, Any]:
    label = (label or "").strip()
    host = (host or "").strip()
    username = (username or "").strip()
    password = password or ""
    if not label or not host or not username or not password:
        raise HTTPException(status_code=400, detail="validation")

    row = ImapMailAccount(
        id=str(uuid4()),
        label=label,
        host=host,
        port=port or (993 if use_ssl else 143),
        use_ssl=use_ssl,
        username=username,
        password_enc=encrypt_secret(password),
        folder=(folder or "INBOX").strip() or "INBOX",
        created_by_id=str(actor.get("id") or actor.get("db_id") or ""),
        created_by_name=str(actor.get("name") or ""),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _account_summary(row)


def update_imap_account(
    db: Session,
    account_id: str,
    *,
    label: str,
    host: str,
    port: int,
    use_ssl: bool,
    username: str,
    password: str,
    folder: str,
) -> dict[str, Any]:
    row = get_imap_account_row(db, account_id)
    label = (label or "").strip()
    host = (host or "").strip()
    username = (username or "").strip()
    if not label or not host or not username:
        raise HTTPException(status_code=400, detail="validation")

    row.label = label
    row.host = host
    row.port = port or (993 if use_ssl else 143)
    row.use_ssl = use_ssl
    row.username = username
    row.folder = (folder or "INBOX").strip() or "INBOX"
    # Blank password on edit means "keep the stored one" - matches the
    # Mailcow/Entra config forms' existing convention.
    if password:
        row.password_enc = encrypt_secret(password)
    db.commit()
    db.refresh(row)
    return _account_summary(row)


def delete_imap_account(db: Session, account_id: str) -> None:
    row = get_imap_account_row(db, account_id)
    db.delete(row)
    db.commit()
