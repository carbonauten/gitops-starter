from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_it_master
from ..mailcow_config_service import clear_stored_mailcow_config, save_mailcow_config
from ..mailcow_service import create_mailbox, delete_mailbox, list_mailboxes, mailcow_status

router = APIRouter(prefix="/api/mail-server", tags=["mail-server"])


class MailcowConfigSave(BaseModel):
    api_url: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(default="", max_length=500)
    default_domain: str = Field(default="", max_length=200)


class MailboxCreate(BaseModel):
    local_part: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(default="", max_length=200)
    display_name: str = Field(default="", max_length=200)
    password: str = Field(..., min_length=8, max_length=200)
    quota_mb: int = Field(default=3072, ge=256, le=51200)


@router.get("/status")
def get_mail_server_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return mailcow_status(db)


@router.put("/config")
def put_mail_server_config(
    payload: MailcowConfigSave,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    status = save_mailcow_config(
        db,
        api_url=payload.api_url,
        api_key=payload.api_key,
        default_domain=payload.default_domain,
        actor=user,
    )
    log_audit(db, entity_type="mail_server", entity_id="config", action="updated", actor=user)
    return status


@router.delete("/config")
def delete_mail_server_config(
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    status = clear_stored_mailcow_config(db)
    log_audit(db, entity_type="mail_server", entity_id="config", action="cleared", actor=user)
    return status


@router.get("/mailboxes")
def get_mailboxes(
    domain: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return {"mailboxes": list_mailboxes(db, domain=domain or "")}


@router.post("/mailboxes", status_code=201)
def post_mailbox(
    payload: MailboxCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    mailbox = create_mailbox(
        db,
        local_part=payload.local_part,
        domain=payload.domain,
        display_name=payload.display_name,
        password=payload.password,
        quota_mb=payload.quota_mb,
    )
    log_audit(
        db,
        entity_type="mail_server",
        entity_id=mailbox["email"],
        action="mailbox_created",
        actor=user,
    )
    return {"mailbox": mailbox}


@router.delete("/mailboxes/{email}", status_code=204)
def delete_mailbox_route(
    email: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
):
    delete_mailbox(db, email=email)
    log_audit(db, entity_type="mail_server", entity_id=email, action="mailbox_deleted", actor=user)
    return Response(status_code=204)
