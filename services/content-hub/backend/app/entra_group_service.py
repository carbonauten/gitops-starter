from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import EntraGroupRoleMapping
from .roles import ALL_ROLES, ROLE_CERT_MANAGER, ROLE_EDITOR, ROLE_IT_MASTER, ROLE_VIEWER

# Highest-priority role wins when a user belongs to groups mapped to several roles.
_ROLE_PRIORITY = {ROLE_IT_MASTER: 0, ROLE_CERT_MANAGER: 1, ROLE_EDITOR: 2, ROLE_VIEWER: 3}


def mapping_to_dict(mapping: EntraGroupRoleMapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "entra_group_id": mapping.entra_group_id,
        "entra_group_name": mapping.entra_group_name,
        "role": mapping.role,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
    }


def list_group_mappings(db: Session) -> list[dict[str, Any]]:
    mappings = db.scalars(
        select(EntraGroupRoleMapping).order_by(EntraGroupRoleMapping.entra_group_name.asc())
    ).all()
    return [mapping_to_dict(mapping) for mapping in mappings]


def create_group_mapping(
    db: Session,
    *,
    entra_group_id: str,
    entra_group_name: str,
    role: str,
) -> EntraGroupRoleMapping:
    group_id = entra_group_id.strip()
    if not group_id or role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    if db.scalar(select(EntraGroupRoleMapping).where(EntraGroupRoleMapping.entra_group_id == group_id)):
        raise HTTPException(status_code=409, detail="mapping_exists")

    mapping = EntraGroupRoleMapping(
        entra_group_id=group_id,
        entra_group_name=entra_group_name.strip(),
        role=role,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def delete_group_mapping(db: Session, mapping_id: str) -> None:
    mapping = db.get(EntraGroupRoleMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(mapping)
    db.commit()


def resolve_role_from_groups(db: Session, group_ids: list[str]) -> str | None:
    """Return the highest-priority platform role mapped to any of the given Entra group ids.

    Returns None when no group id has a mapping, so callers can leave the user's
    existing role untouched instead of falling back to a default.
    """
    if not group_ids:
        return None
    mappings = db.scalars(
        select(EntraGroupRoleMapping).where(EntraGroupRoleMapping.entra_group_id.in_(group_ids))
    ).all()
    if not mappings:
        return None
    return min((mapping.role for mapping in mappings), key=lambda role: _ROLE_PRIORITY.get(role, 99))
