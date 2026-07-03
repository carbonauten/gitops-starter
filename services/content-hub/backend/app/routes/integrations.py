from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import get_session, new_oauth_state, set_session
from ..database import get_db
from ..dependencies import require_it_master
from ..integrations_service import (
    complete_microsoft_connection,
    complete_notion_connection,
    disconnect_integration,
    integrations_overview,
    list_microsoft_channels,
    list_microsoft_teams,
    list_notion_databases,
    microsoft_authorize_url,
    notion_authorize_url,
)
from ..publish_service import update_publish_settings

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _publish_redirect(status: str, provider: str) -> RedirectResponse:
    return RedirectResponse(url=f"/publish?integration={provider}&status={status}", status_code=302)


@router.get("/status")
def integration_status_route(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return integrations_overview(db)


@router.get("/microsoft/connect")
async def microsoft_connect(request: Request) -> RedirectResponse:
    state = new_oauth_state()
    session = get_session(request) or {}
    session["integration_oauth_state"] = state
    session["integration_provider"] = "microsoft"
    response = RedirectResponse(url=microsoft_authorize_url(state), status_code=302)
    set_session(response, session)
    return response


@router.get("/microsoft/callback")
async def microsoft_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    session = get_session(request) or {}
    expected_state = session.get("integration_oauth_state")
    if not code or not state or state != expected_state:
        return _publish_redirect("error", "microsoft")

    user = session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        result = await complete_microsoft_connection(db, code=code, connected_by=user)
        update_publish_settings(
            db,
            {
                "outlook_enabled": True,
                "outlook_sender_id": result["outlook_sender_id"],
            },
        )
    except HTTPException:
        return _publish_redirect("error", "microsoft")

    response = _publish_redirect("success", "microsoft")
    session.pop("integration_oauth_state", None)
    session.pop("integration_provider", None)
    set_session(response, session)
    return response


@router.delete("/microsoft")
def microsoft_disconnect(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    disconnect_integration(db, "microsoft")
    update_publish_settings(
        db,
        {
            "teams_enabled": False,
            "teams_team_id": "",
            "teams_channel_id": "",
            "outlook_enabled": False,
            "outlook_sender_id": "",
        },
    )
    return {"ok": True}


@router.get("/microsoft/teams")
async def microsoft_teams(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return {"teams": await list_microsoft_teams(db)}


@router.get("/microsoft/teams/{team_id}/channels")
async def microsoft_channels(
    team_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return {"channels": await list_microsoft_channels(db, team_id)}


@router.get("/notion/connect")
async def notion_connect(request: Request) -> RedirectResponse:
    state = new_oauth_state()
    session = get_session(request) or {}
    session["integration_oauth_state"] = state
    session["integration_provider"] = "notion"
    response = RedirectResponse(url=notion_authorize_url(state), status_code=302)
    set_session(response, session)
    return response


@router.get("/notion/callback")
async def notion_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: Optional[str] = None,
    state: Optional[str] = None,
) -> RedirectResponse:
    session = get_session(request) or {}
    expected_state = session.get("integration_oauth_state")
    if not code or not state or state != expected_state:
        return _publish_redirect("error", "notion")

    user = session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        await complete_notion_connection(db, code=code, connected_by=user)
        update_publish_settings(db, {"notion_enabled": True})
    except HTTPException:
        return _publish_redirect("error", "notion")

    response = _publish_redirect("success", "notion")
    session.pop("integration_oauth_state", None)
    session.pop("integration_provider", None)
    set_session(response, session)
    return response


@router.delete("/notion")
def notion_disconnect(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    disconnect_integration(db, "notion")
    update_publish_settings(
        db,
        {
            "notion_enabled": False,
            "notion_database_id": "",
        },
    )
    return {"ok": True}


@router.get("/notion/databases")
async def notion_databases(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    return {"databases": await list_notion_databases(db)}
