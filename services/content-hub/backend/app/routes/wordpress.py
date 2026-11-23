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
)

router = APIRouter(prefix="/api/wordpress", tags=["wordpress"])


class WordPressInstallRequest(BaseModel):
    mode: str = Field(..., description="flexibility or security")
    domain: str = Field(..., min_length=1, max_length=200)


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
    language = getattr(request.state, "language", "de")
    try:
        installations = await list_wordpress_installations(db)
    except WordPressAutomationError as exc:
        message = translate(f"errors.{exc.code}", language)
        if message == f"errors.{exc.code}":
            message = translate("errors.generic", language)
        return JSONResponse(
            status_code=502,
            content={"error": message, "code": exc.code, "screenshot_base64": exc.screenshot_base64},
        )
    return {"installations": installations}


@router.post("/install")
async def post_install(
    payload: WordPressInstallRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_wordpress_manager),
):
    if payload.mode not in INSTALL_MODES:
        return JSONResponse(status_code=400, content={"error": "validation", "code": "validation"})

    language = getattr(request.state, "language", "de")
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
        message = translate(f"errors.{exc.code}", language)
        if message == f"errors.{exc.code}":
            message = translate("errors.generic", language)
        return JSONResponse(
            status_code=502,
            content={"error": message, "code": exc.code, "screenshot_base64": exc.screenshot_base64},
        )

    log_audit(
        db,
        entity_type="wordpress_automation",
        entity_id=payload.domain,
        action="installed",
        actor=user,
        details={"mode": payload.mode},
    )
    return {"installation": result}
