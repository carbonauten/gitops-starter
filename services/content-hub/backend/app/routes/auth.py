from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from ..auth import (
    clear_session,
    entra_authorize_url,
    exchange_code_for_user,
    get_session,
    mock_user,
    new_oauth_state,
    require_user,
    set_session,
)
from ..config import get_settings
from ..i18n import normalize_language, translate

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    settings = get_settings()
    language = normalize_language(request.query_params.get("lang"))

    if settings.entra_mock_auth or not settings.entra_configured:
        response = RedirectResponse(url="/", status_code=302)
        set_session(response, {"user": mock_user(language), "oauth_state": None})
        return response

    state = new_oauth_state()
    response = RedirectResponse(url=entra_authorize_url(state), status_code=302)
    set_session(response, {"oauth_state": state})
    return response


@router.get("/callback")
async def callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    settings = get_settings()
    if settings.entra_mock_auth or not settings.entra_configured:
        response = RedirectResponse(url="/", status_code=302)
        set_session(response, {"user": mock_user()})
        return response

    session = get_session(request) or {}
    expected_state = session.get("oauth_state")
    if not code or not state or state != expected_state:
        raise HTTPException(status_code=400, detail="invalid_oauth_state")

    user = await exchange_code_for_user(code)
    response = RedirectResponse(url="/", status_code=302)
    set_session(response, {"user": user})
    return response


@router.get("/me")
def me(request: Request) -> dict:
    user = require_user(request)
    return {"user": user}


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    clear_session(response)
    return response
