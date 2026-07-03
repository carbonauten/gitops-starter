from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import AuditLog


def log_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    actor: dict,
    details: Optional[dict[str, Any]] = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor.get("id", ""),
        actor_name=actor.get("name", ""),
        actor_email=actor.get("email", ""),
        details=json.dumps(details or {}, ensure_ascii=False)[:4000],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def audit_entry_to_dict(entry: AuditLog) -> dict:
    details: dict[str, Any] = {}
    if entry.details:
        try:
            details = json.loads(entry.details)
        except json.JSONDecodeError:
            details = {"message": entry.details}
    return {
        "id": entry.id,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action": entry.action,
        "actor_id": entry.actor_id,
        "actor_name": entry.actor_name,
        "actor_email": entry.actor_email,
        "details": details,
        "created_at": entry.created_at.isoformat(),
    }


def list_audit_entries(
    db: Session,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    entries = db.scalars(stmt).all()
    return [audit_entry_to_dict(entry) for entry in entries]
