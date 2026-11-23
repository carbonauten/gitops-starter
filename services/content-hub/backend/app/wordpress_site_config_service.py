from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import WordPressSite
from .user_integration_store import decrypt_secret, encrypt_secret


@dataclass(frozen=True)
class WordPressSiteCredentials:
    id: str
    label: str
    base_url: str
    username: str
    app_password: str


def _site_summary(row: WordPressSite) -> dict[str, Any]:
    return {
        "id": row.id,
        "label": row.label,
        "base_url": row.base_url,
        "username": row.username,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_wordpress_sites(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(WordPressSite).order_by(WordPressSite.label)).all()
    return [_site_summary(row) for row in rows]


def get_wordpress_site_row(db: Session, site_id: str) -> WordPressSite:
    row = db.get(WordPressSite, site_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    return row


def get_wordpress_site_credentials(db: Session, site_id: str) -> WordPressSiteCredentials:
    row = get_wordpress_site_row(db, site_id)
    return WordPressSiteCredentials(
        id=row.id,
        label=row.label,
        base_url=row.base_url,
        username=row.username,
        app_password=decrypt_secret(row.app_password_enc or ""),
    )


def create_wordpress_site(
    db: Session,
    *,
    label: str,
    base_url: str,
    username: str,
    app_password: str,
    actor: dict[str, Any],
) -> dict[str, Any]:
    label = (label or "").strip()
    base_url = (base_url or "").strip().rstrip("/")
    username = (username or "").strip()
    app_password = app_password or ""
    if not label or not base_url or not username or not app_password:
        raise HTTPException(status_code=400, detail="validation")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="validation")

    row = WordPressSite(
        id=str(uuid4()),
        label=label,
        base_url=base_url,
        username=username,
        app_password_enc=encrypt_secret(app_password),
        created_by_id=str(actor.get("id") or actor.get("db_id") or ""),
        created_by_name=str(actor.get("name") or ""),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _site_summary(row)


def delete_wordpress_site(db: Session, site_id: str) -> None:
    row = get_wordpress_site_row(db, site_id)
    db.delete(row)
    db.commit()
