from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import (
    clear_session,
    entra_authorize_url,
    exchange_code_for_user,
    get_session,
    mock_user,
    new_oauth_state,
    set_session,
)
from ..config import get_settings
from ..database import get_db
from ..dependencies import get_current_user
from ..i18n import normalize_language
from ..user_service import enrich_user_session, upsert_user_from_login

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _login_user(db: Session, *, entra_id: str, email: str, name: str, language: str | None) -> dict:
    user = upsert_user_from_login(
        db,
        entra_id=entra_id,
        email=email,
        name=name,
        language=language,
    )
    return enrich_user_session(db, user)


@router.get("/login")
async def login(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    settings = get_settings()
    language = normalize_language(request.query_params.get("lang"))

    if settings.entra_mock_auth or not settings.entra_configured:
        profile = mock_user(language)
        user = _login_user(
            db,
            entra_id=profile["id"],
            email=profile["email"],
            name=profile["name"],
            language=profile["language"],
        )
        response = RedirectResponse(url="/", status_code=302)
        set_session(response, {"user": user, "oauth_state": None})
        return response

    state = new_oauth_state()
    response = RedirectResponse(url=entra_authorize_url(state), status_code=302)
    set_session(response, {"oauth_state": state})
    return response


@router.get("/callback")
async def callback(
    request: Request,
    db: Session = Depends(get_db),
    code: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    settings = get_settings()
    if settings.entra_mock_auth or not settings.entra_configured:
        profile = mock_user()
        user = _login_user(
            db,
            entra_id=profile["id"],
            email=profile["email"],
            name=profile["name"],
            language=profile["language"],
        )
        response = RedirectResponse(url="/", status_code=302)
        set_session(response, {"user": user})
        return response

    session = get_session(request) or {}
    expected_state = session.get("oauth_state")
    if not code or not state or state != expected_state:
        raise HTTPException(status_code=400, detail="invalid_oauth_state")

    profile = await exchange_code_for_user(code)
    user = _login_user(
        db,
        entra_id=profile["id"],
        email=profile["email"],
        name=profile["name"],
        language=profile.get("language"),
    )
    response = RedirectResponse(url="/", status_code=302)
    set_session(response, {"user": user})
    return response


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": user}


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=204)
    clear_session(response)
    return response
