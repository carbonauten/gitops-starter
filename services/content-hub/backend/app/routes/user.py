from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_session, set_session
from ..config import get_settings
from ..database import UserAccount, get_db
from ..dependencies import get_current_user, require_it_master
from ..i18n import normalize_language, translate
from ..roles import ALL_ROLES
from ..user_service import (
    create_user_account,
    enrich_user_session,
    list_users,
    update_user_active,
    update_user_department,
    update_user_password,
    update_user_role,
    users_to_sessions,
)

router = APIRouter(prefix="/api/user", tags=["user"])


class LanguageUpdate(BaseModel):
    language: str = Field(..., description="de, en, or zh-CN")


class RoleUpdate(BaseModel):
    role: str = Field(..., description="it_master, editor, or viewer")


class ActiveUpdate(BaseModel):
    is_active: bool


class DepartmentUpdate(BaseModel):
    department_id: Optional[str] = None


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(..., description="it_master, editor, or viewer")
    department_id: Optional[str] = None


class PasswordUpdate(BaseModel):
    password: str = Field(..., min_length=8, max_length=200)


@router.patch("/language")
def update_language(
    payload: LanguageUpdate,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    session_user: dict = Depends(get_current_user),
) -> dict:
    language = normalize_language(payload.language)
    if language not in get_settings().supported_languages:
        raise HTTPException(status_code=400, detail="invalid_language")

    user = db.get(UserAccount, session_user["db_id"])
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    user.language = language
    db.commit()
    db.refresh(user)

    updated = enrich_user_session(db, user)
    session = get_session(request) or {}
    session["user"] = updated
    set_session(response, session)

    return {
        "user": updated,
        "message": translate("messages.language_updated", language),
    }


@router.get("/users")
def get_users(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    users = list_users(db)
    return {"users": users_to_sessions(db, users)}


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    user = create_user_account(
        db,
        email=payload.email,
        name=payload.name,
        password=payload.password,
        role=payload.role,
        department_id=payload.department_id,
    )
    return {"user": enrich_user_session(db, user)}


@router.patch("/users/{user_id}/role")
def set_user_role(
    user_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    user = update_user_role(db, user_id, payload.role)
    return {"user": enrich_user_session(db, user)}


@router.patch("/users/{user_id}/active")
def set_user_active(
    user_id: str,
    payload: ActiveUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    user = update_user_active(db, user_id, payload.is_active)
    return {"user": enrich_user_session(db, user)}


@router.patch("/users/{user_id}/department")
def set_user_department(
    user_id: str,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    user = update_user_department(db, user_id, payload.department_id)
    return {"user": enrich_user_session(db, user)}


@router.patch("/users/{user_id}/password")
def set_user_password(
    user_id: str,
    payload: PasswordUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    user = update_user_password(db, user_id, payload.password)
    return {"user": enrich_user_session(db, user)}
