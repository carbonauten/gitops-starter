from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_it_master
from ..i18n import translate
from ..strato_automation_service import (
    StratoAutomationError,
    create_mailbox_via_automation,
    resume_create_mailbox_via_automation,
)
from ..strato_config_service import (
    clear_stored_strato_config,
    save_strato_config,
    save_strato_domains,
    strato_status,
)

router = APIRouter(prefix="/api/strato-automation", tags=["strato-automation"])


class StratoConfigSave(BaseModel):
    customer_number: str = Field(..., min_length=1, max_length=100)
    password: str = Field(default="", max_length=300)


class StratoDomainsSave(BaseModel):
    domains: str = Field(default="", max_length=2000)


class StratoCreateMailboxRequest(BaseModel):
    local_part: str = Field(..., min_length=1, max_length=100)
    domain: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)


class StratoCaptchaResumeRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    captcha_code: str = Field(..., min_length=1, max_length=32)


@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return strato_status(db)


@router.put("/config")
def put_config(
    payload: StratoConfigSave,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    status = save_strato_config(db, customer_number=payload.customer_number, password=payload.password, actor=user)
    log_audit(db, entity_type="strato_automation", entity_id="config", action="updated", actor=user)
    return status


@router.put("/domains")
def put_domains(
    payload: StratoDomainsSave,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    status = save_strato_domains(db, domains=payload.domains, actor=user)
    log_audit(db, entity_type="strato_automation", entity_id="domains", action="updated", actor=user)
    return status


@router.delete("/config")
def delete_config(
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    status = clear_stored_strato_config(db)
    log_audit(db, entity_type="strato_automation", entity_id="config", action="cleared", actor=user)
    return status


def _translated_automation_error(request: Request, exc: StratoAutomationError) -> JSONResponse:
    language = getattr(request.state, "language", "de")
    message = translate(f"errors.{exc.code}", language)
    if message == f"errors.{exc.code}":
        message = translate("errors.generic", language)
    return JSONResponse(
        status_code=502,
        content={"error": message, "code": exc.code, "screenshot_base64": exc.screenshot_base64},
    )


@router.post("/create-mailbox")
async def post_create_mailbox(
    payload: StratoCreateMailboxRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
):
    try:
        result = await create_mailbox_via_automation(
            db,
            local_part=payload.local_part,
            domain=payload.domain,
            password=payload.password,
        )
    except StratoAutomationError as exc:
        log_audit(
            db,
            entity_type="strato_automation",
            entity_id=f"{payload.local_part}@{payload.domain}",
            action="create_failed",
            actor=user,
            details={"code": exc.code},
        )
        return _translated_automation_error(request, exc)

    if result["status"] == "captcha_required":
        return result

    log_audit(
        db,
        entity_type="strato_automation",
        entity_id=result["email"],
        action="mailbox_created",
        actor=user,
    )
    return {"mailbox": result}


@router.post("/create-mailbox/captcha")
async def post_create_mailbox_captcha(
    payload: StratoCaptchaResumeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
):
    try:
        result = await resume_create_mailbox_via_automation(payload.session_id, payload.captcha_code)
    except StratoAutomationError as exc:
        log_audit(
            db,
            entity_type="strato_automation",
            entity_id=payload.session_id,
            action="create_failed",
            actor=user,
            details={"code": exc.code},
        )
        return _translated_automation_error(request, exc)

    log_audit(
        db,
        entity_type="strato_automation",
        entity_id=result["email"],
        action="mailbox_created",
        actor=user,
    )
    return {"mailbox": result}
