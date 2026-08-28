from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..auth import get_session, set_session
from ..config import get_settings
from ..database import UserAccount, get_db
from ..dependencies import get_current_user, require_it_master
from ..entra_group_service import (
    create_group_mapping,
    delete_group_mapping,
    list_group_mappings,
    mapping_to_dict,
)
from ..i18n import normalize_language, translate
from ..roles import ALL_ROLES
from ..invite_service import (
    create_invite,
    list_invites,
    queue_invite_email,
    resend_invite,
    revoke_invite,
)
from ..user_service import (
    create_user_account,
    enrich_user_session,
    list_users,
    update_user_active,
    update_user_department,
    update_user_password,
    update_user_role,
    update_user_shop_access,
    users_to_sessions,
)

router = APIRouter(prefix="/api/user", tags=["user"])


class LanguageUpdate(BaseModel):
    language: str = Field(..., description="de, en, or zh-CN")


class RoleUpdate(BaseModel):
    role: str = Field(..., description="it_master, editor, certificate_manager, or viewer")


class ActiveUpdate(BaseModel):
    is_active: bool


class DepartmentUpdate(BaseModel):
    department_id: Optional[str] = None


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    role: str = Field(..., description="it_master, editor, certificate_manager, or viewer")
    department_id: Optional[str] = None
    can_manage_shop: bool = False


class PasswordUpdate(BaseModel):
    password: str = Field(..., min_length=8, max_length=200)


class ShopAccessUpdate(BaseModel):
    can_manage_shop: bool


class InviteCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    role: str = Field(..., description="it_master, editor, certificate_manager, or viewer")
    department_id: Optional[str] = None


class GroupMappingCreate(BaseModel):
    entra_group_id: str = Field(..., min_length=1, max_length=100)
    entra_group_name: str = Field(default="", max_length=200)
    role: str = Field(..., description="it_master, editor, certificate_manager, or viewer")


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
        can_manage_shop=payload.can_manage_shop,
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


@router.patch("/users/{user_id}/shop-access")
def set_user_shop_access(
    user_id: str,
    payload: ShopAccessUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    user = update_user_shop_access(db, user_id, payload.can_manage_shop)
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


@router.get("/invites")
def get_invites(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return {"invites": list_invites(db)}


@router.post("/invites")
def send_invite(
    payload: InviteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_it_master),
) -> dict:
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    invite = create_invite(
        db,
        email=payload.email,
        role=payload.role,
        department_id=payload.department_id,
        invited_by_id=admin["db_id"],
        invited_by_name=admin["name"],
    )
    if invite.get("email_pending"):
        background_tasks.add_task(
            queue_invite_email,
            to_email=invite["email"],
            invite_url=invite["invite_url"],
            role=invite["role"],
            invited_by_name=admin["name"],
        )
    return {"invite": invite}


@router.post("/invites/{invite_id}/resend")
def resend_user_invite(
    invite_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_it_master),
) -> dict:
    invite = resend_invite(db, invite_id)
    if invite.get("email_pending"):
        background_tasks.add_task(
            queue_invite_email,
            to_email=invite["email"],
            invite_url=invite["invite_url"],
            role=invite["role"],
            invited_by_name=admin["name"],
        )
    return {"invite": invite}


@router.delete("/invites/{invite_id}")
def delete_invite(
    invite_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> Response:
    revoke_invite(db, invite_id)
    return Response(status_code=204)


@router.get("/group-mappings")
def get_group_mappings(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return {"mappings": list_group_mappings(db)}


@router.post("/group-mappings")
def create_group_mapping_route(
    payload: GroupMappingCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_it_master),
) -> dict:
    if payload.role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    mapping = create_group_mapping(
        db,
        entra_group_id=payload.entra_group_id,
        entra_group_name=payload.entra_group_name,
        role=payload.role,
    )
    log_audit(
        db,
        entity_type="entra_group_mapping",
        entity_id=mapping.id,
        action="create",
        actor=admin,
        details={"entra_group_id": mapping.entra_group_id, "role": mapping.role},
    )
    return {"mapping": mapping_to_dict(mapping)}


@router.delete("/group-mappings/{mapping_id}")
def delete_group_mapping_route(
    mapping_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_it_master),
) -> Response:
    delete_group_mapping(db, mapping_id)
    log_audit(
        db,
        entity_type="entra_group_mapping",
        entity_id=mapping_id,
        action="delete",
        actor=admin,
        details={},
    )
    return Response(status_code=204)
