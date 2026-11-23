from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..database import get_db
from ..dependencies import require_wordpress_manager
from ..i18n import translate
from ..strato_config_service import strato_status
from ..wordpress_automation_service import (
    INSTALL_MODES,
    WordPressAutomationError,
    install_wordpress_via_automation,
    list_wordpress_installations,
    resume_install_wordpress_via_automation,
    resume_list_wordpress_installations,
)

router = APIRouter(prefix="/api/wordpress", tags=["wordpress"])


class WordPressInstallRequest(BaseModel):
    mode: str = Field(..., description="flexibility or security")
    domain: str = Field(..., min_length=1, max_length=200)


class WordPressCaptchaResumeRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    captcha_code: str = Field(..., min_length=1, max_length=32)


def _translated_automation_error(request: Request, exc: WordPressAutomationError) -> JSONResponse:
    language = getattr(request.state, "language", "de")
    message = translate(f"errors.{exc.code}", language)
    if message == f"errors.{exc.code}":
        message = translate("errors.generic", language)
    return JSONResponse(
        status_code=502,
        content={"error": message, "code": exc.code, "screenshot_base64": exc.screenshot_base64},
    )


@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
) -> dict:
    # WordPress automation reuses the same Strato customer login already
    # stored for mailbox automation - no separate credential store.
    return strato_status(db)


@router.get("/installations")
async def get_installations(
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_wordpress_manager),
):
    try:
        result = await list_wordpress_installations(db)
    except WordPressAutomationError as exc:
        return _translated_automation_error(request, exc)
    if result["status"] == "captcha_required":
        return result
    return {"installations": result["installations"]}


@router.post("/installations/captcha")
async def post_installations_captcha(
    payload: WordPressCaptchaResumeRequest,
    request: Request,
    _user: dict = Depends(require_wordpress_manager),
):
    try:
        result = await resume_list_wordpress_installations(payload.session_id, payload.captcha_code)
    except WordPressAutomationError as exc:
        return _translated_automation_error(request, exc)
    return {"installations": result["installations"]}


@router.post("/install")
async def post_install(
    payload: WordPressInstallRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
):
    if payload.mode not in INSTALL_MODES:
        return JSONResponse(status_code=400, content={"error": "validation", "code": "validation"})

    try:
        result = await install_wordpress_via_automation(db, mode=payload.mode, domain=payload.domain)
    except WordPressAutomationError as exc:
        log_audit(
            db,
            entity_type="wordpress_automation",
            entity_id=payload.domain,
            action="install_failed",
            actor=user,
            details={"code": exc.code, "mode": payload.mode},
        )
        return _translated_automation_error(request, exc)

    if result["status"] == "captcha_required":
        return result

    log_audit(
        db,
        entity_type="wordpress_automation",
        entity_id=payload.domain,
        action="installed",
        actor=user,
        details={"mode": payload.mode},
    )
    return {"installation": result}


@router.post("/install/captcha")
async def post_install_captcha(
    payload: WordPressCaptchaResumeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
):
    try:
        result = await resume_install_wordpress_via_automation(payload.session_id, payload.captcha_code)
    except WordPressAutomationError as exc:
        log_audit(
            db,
            entity_type="wordpress_automation",
            entity_id=payload.session_id,
            action="install_failed",
            actor=user,
            details={"code": exc.code},
        )
        return _translated_automation_error(request, exc)

    log_audit(
        db,
        entity_type="wordpress_automation",
        entity_id=result["domain"],
        action="installed",
        actor=user,
        details={"mode": result["mode"]},
    )
    return {"installation": result}
