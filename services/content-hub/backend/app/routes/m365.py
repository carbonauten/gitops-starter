from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_it_master
from ..graph_directory_service import (
    assign_license,
    create_directory_user,
    directory_status,
    get_directory_user,
    list_available_licenses,
    list_directory_groups,
    list_directory_users,
    remove_license,
    reset_directory_password,
    set_directory_user_enabled,
)
from ..m365_ai_service import handle_directory_question, looks_like_m365_admin_question

router = APIRouter(prefix="/api/m365", tags=["m365"])


class LicenseAssignRequest(BaseModel):
    sku_id: str = Field(..., min_length=1, max_length=200)


class DirectoryUserCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=200)
    user_principal_name: str = Field(..., min_length=3, max_length=200)
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)
    job_title: str = Field(default="", max_length=200)
    department: str = Field(default="", max_length=200)
    usage_location: str = Field(default="DE", max_length=2)


class DirectoryEnabledUpdate(BaseModel):
    account_enabled: bool


class DirectoryPasswordReset(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)


class DirectoryAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    language: str = "de"


@router.get("/status")
async def m365_status(_user: dict = Depends(require_it_master)) -> dict:
    payload = directory_status()
    payload["assistant_name"] = "Ask Carbonauten"
    return payload


@router.get("/users")
async def m365_users(
    q: str = "",
    _user: dict = Depends(require_it_master),
) -> dict:
    users = await list_directory_users(query=q)
    status = directory_status()
    return {"users": users, "mock": status["mock"], "graph_configured": status["graph_configured"]}


@router.get("/users/{user_id}")
async def m365_user(user_id: str, _user: dict = Depends(require_it_master)) -> dict:
    return {"user": await get_directory_user(user_id)}


@router.post("/users")
async def m365_create_user(
    payload: DirectoryUserCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    created, temporary_password = await create_directory_user(
        display_name=payload.display_name,
        user_principal_name=payload.user_principal_name,
        password=payload.password,
        job_title=payload.job_title,
        department=payload.department,
        usage_location=payload.usage_location,
    )
    log_audit(
        db,
        entity_type="m365_user",
        entity_id=created["id"],
        action="create",
        actor=user,
        details={"upn": created["user_principal_name"]},
    )
    return {"user": created, "temporary_password": temporary_password}


@router.patch("/users/{user_id}/enabled")
async def m365_set_enabled(
    user_id: str,
    payload: DirectoryEnabledUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    updated = await set_directory_user_enabled(user_id, payload.account_enabled)
    log_audit(
        db,
        entity_type="m365_user",
        entity_id=updated["id"],
        action="enable" if payload.account_enabled else "disable",
        actor=user,
        details={"upn": updated["user_principal_name"], "account_enabled": payload.account_enabled},
    )
    return {"user": updated}


@router.post("/users/{user_id}/reset-password")
async def m365_reset_password(
    user_id: str,
    payload: DirectoryPasswordReset = DirectoryPasswordReset(),
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    password = payload.password
    updated, temporary_password = await reset_directory_password(user_id, password=password)
    log_audit(
        db,
        entity_type="m365_user",
        entity_id=updated["id"],
        action="reset_password",
        actor=user,
        details={"upn": updated["user_principal_name"]},
    )
    return {"user": updated, "temporary_password": temporary_password}


@router.get("/groups")
async def m365_groups(q: str = "", _user: dict = Depends(require_it_master)) -> dict:
    return {"groups": await list_directory_groups(query=q)}


@router.get("/licenses")
async def m365_licenses(_user: dict = Depends(require_it_master)) -> dict:
    return {"licenses": await list_available_licenses()}


@router.post("/users/{user_id}/licenses")
async def m365_assign_license(
    user_id: str,
    payload: LicenseAssignRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    updated = await assign_license(user_id, payload.sku_id)
    log_audit(
        db,
        entity_type="m365_user",
        entity_id=updated["id"],
        action="assign_license",
        actor=user,
        details={"upn": updated["user_principal_name"], "sku_id": payload.sku_id},
    )
    return {"user": updated}


@router.delete("/users/{user_id}/licenses/{sku_id}")
async def m365_remove_license(
    user_id: str,
    sku_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    updated = await remove_license(user_id, sku_id)
    log_audit(
        db,
        entity_type="m365_user",
        entity_id=updated["id"],
        action="remove_license",
        actor=user,
        details={"upn": updated["user_principal_name"], "sku_id": sku_id},
    )
    return {"user": updated}


@router.post("/ask")
async def m365_ask(
    payload: DirectoryAskRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    result = await handle_directory_question(payload.question, language=payload.language or user.get("language") or "de")
    if result.get("action") in {"create", "disable", "enable", "reset_password"} and result.get("user"):
        log_audit(
            db,
            entity_type="m365_user",
            entity_id=result["user"]["id"],
            action=f"ai_{result['action']}",
            actor=user,
            details={"question": payload.question[:300], "upn": result["user"].get("user_principal_name")},
        )
    return {
        "question": payload.question,
        "answer": result["answer"],
        "action": result["action"],
        "users": result.get("users") or [],
        "user": result.get("user"),
        "temporary_password": result.get("temporary_password") or "",
        "recognized": looks_like_m365_admin_question(payload.question),
        "assistant_name": "Ask Carbonauten",
    }
