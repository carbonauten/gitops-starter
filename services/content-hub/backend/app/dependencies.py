from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .roles import ADMIN_ROLES, EDIT_ROLES
from .user_service import enrich_user_session, get_user_by_entra_id, sync_master_role_from_env


def _session_user(request: Request) -> dict[str, Any]:
    from .auth import get_session

    session = get_session(request)
    if not session or "user" not in session:
        raise HTTPException(status_code=401, detail="unauthorized")
    return session["user"]


def get_current_user(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    session_user = _session_user(request)
    entra_id = session_user.get("id")
    if not entra_id:
        raise HTTPException(status_code=401, detail="unauthorized")

    user = get_user_by_entra_id(db, entra_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="unauthorized")
    user = sync_master_role_from_env(db, user)
    return enrich_user_session(db, user)


def require_editor(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") not in EDIT_ROLES:
        raise HTTPException(status_code=403, detail="forbidden")
    return user


def require_it_master(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="forbidden")
    return user
