from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .integration_store import (
    delete_integration,
    get_integration,
    read_access_token,
    read_refresh_token,
    save_integration,
)

logger = logging.getLogger(__name__)

MICROSOFT_PUBLISH_SCOPES = (
    "offline_access User.Read Team.ReadBasic.All Channel.ReadBasic.All "
    "ChannelMessage.Send Mail.ReadWrite"
)


def microsoft_redirect_uri(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    origin = settings.effective_public_origin or "http://localhost:8080"
    return f"{origin.rstrip('/')}/api/integrations/microsoft/callback"


def notion_redirect_uri(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    origin = settings.effective_public_origin or "http://localhost:8080"
    return f"{origin.rstrip('/')}/api/integrations/notion/callback"


def microsoft_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.entra_configured:
        raise HTTPException(status_code=400, detail="microsoft_auth_unavailable")
    params = {
        "client_id": settings.azure_client_id,
        "response_type": "code",
        "redirect_uri": microsoft_redirect_uri(settings),
        "response_mode": "query",
        "scope": MICROSOFT_PUBLISH_SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/authorize?"
        f"{urlencode(params)}"
    )


def notion_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.notion_oauth_configured:
        raise HTTPException(status_code=400, detail="notion_oauth_unavailable")
    params = {
        "client_id": settings.notion_client_id,
        "response_type": "code",
        "owner": "user",
        "redirect_uri": notion_redirect_uri(settings),
        "state": state,
    }
    return f"https://api.notion.com/v1/oauth/authorize?{urlencode(params)}"


async def _exchange_microsoft_code(code: str, settings: Settings) -> dict[str, Any]:
    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": microsoft_redirect_uri(settings),
        "scope": MICROSOFT_PUBLISH_SCOPES,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            logger.error("Microsoft integration token failed: %s", response.text)
            raise HTTPException(status_code=502, detail="integration_token_failed")
        return response.json()


async def _exchange_notion_code(code: str, settings: Settings) -> dict[str, Any]:
    credentials = base64.b64encode(
        f"{settings.notion_client_id}:{settings.notion_client_secret}".encode()
    ).decode()
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": notion_redirect_uri(settings),
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code != 200:
            logger.error("Notion integration token failed: %s", response.text)
            raise HTTPException(status_code=502, detail="integration_token_failed")
        return response.json()


def _expires_at_from_payload(payload: dict[str, Any]) -> datetime | None:
    expires_in = payload.get("expires_in")
    if not expires_in:
        return None
    try:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in) - 60)
    except (TypeError, ValueError):
        return None


async def complete_microsoft_connection(
    db: Session,
    *,
    code: str,
    connected_by: dict,
) -> dict[str, Any]:
    settings = get_settings()
    payload = await _exchange_microsoft_code(code, settings)
    access_token = payload.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="integration_token_failed")

    async with httpx.AsyncClient(timeout=20.0) as client:
        profile_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_response.status_code != 200:
            raise HTTPException(status_code=502, detail="profile_fetch_failed")
        profile = profile_response.json()

    email = profile.get("mail") or profile.get("userPrincipalName") or ""
    user_id = profile.get("id", "")
    display_name = profile.get("displayName") or email

    save_integration(
        db,
        provider="microsoft",
        access_token=access_token,
        refresh_token=payload.get("refresh_token", ""),
        expires_at=_expires_at_from_payload(payload),
        account_label=email or display_name,
        connected_by_id=connected_by.get("db_id", ""),
        connected_by_name=connected_by.get("name", ""),
    )

    return {
        "provider": "microsoft",
        "account": email or display_name,
        "outlook_sender_id": user_id or email,
    }


async def complete_notion_connection(
    db: Session,
    *,
    code: str,
    connected_by: dict,
) -> dict[str, Any]:
    settings = get_settings()
    payload = await _exchange_notion_code(code, settings)
    access_token = payload.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="integration_token_failed")

    workspace_name = ""
    owner = payload.get("workspace_name") or payload.get("workspace_id")
    if isinstance(owner, str):
        workspace_name = owner

    save_integration(
        db,
        provider="notion",
        access_token=access_token,
        refresh_token="",
        expires_at=None,
        account_label=workspace_name,
        connected_by_id=connected_by.get("db_id", ""),
        connected_by_name=connected_by.get("name", ""),
    )

    return {"provider": "notion", "account": workspace_name}


async def refresh_microsoft_access_token(db: Session) -> str:
    row = get_integration(db, "microsoft")
    if not row:
        raise HTTPException(status_code=400, detail="integration_not_connected")

    access_token = read_access_token(row)
    if row.expires_at and row.expires_at > datetime.now(timezone.utc) and access_token:
        return access_token

    refresh_token = read_refresh_token(row)
    if not refresh_token:
        return access_token

    settings = get_settings()
    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": MICROSOFT_PUBLISH_SCOPES,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            logger.error("Microsoft token refresh failed: %s", response.text)
            raise HTTPException(status_code=502, detail="integration_token_failed")
        payload = response.json()

    new_access = payload.get("access_token", "")
    if not new_access:
        raise HTTPException(status_code=502, detail="integration_token_failed")

    save_integration(
        db,
        provider="microsoft",
        access_token=new_access,
        refresh_token=payload.get("refresh_token", refresh_token),
        expires_at=_expires_at_from_payload(payload),
        account_label=row.account_label,
        connected_by_id=row.connected_by_id,
        connected_by_name=row.connected_by_name,
    )
    return new_access


async def get_microsoft_access_token(db: Session) -> str | None:
    row = get_integration(db, "microsoft")
    if not row:
        return None
    return await refresh_microsoft_access_token(db)


def get_notion_access_token(db: Session) -> str | None:
    row = get_integration(db, "notion")
    if not row:
        return None
    token = read_access_token(row)
    return token or None


async def list_microsoft_teams(db: Session) -> list[dict[str, str]]:
    token = await get_microsoft_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="integration_not_connected")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/joinedTeams",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="graph_request_failed")
        payload = response.json()

    teams = []
    for item in payload.get("value", []):
        team_id = item.get("id", "")
        if team_id:
            teams.append({"id": team_id, "name": item.get("displayName", team_id)})
    return teams


async def list_microsoft_channels(db: Session, team_id: str) -> list[dict[str, str]]:
    token = await get_microsoft_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="integration_not_connected")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="graph_request_failed")
        payload = response.json()

    channels = []
    for item in payload.get("value", []):
        channel_id = item.get("id", "")
        if channel_id:
            channels.append({"id": channel_id, "name": item.get("displayName", channel_id)})
    return channels


async def list_notion_databases(db: Session) -> list[dict[str, str]]:
    token = get_notion_access_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="integration_not_connected")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.notion.com/v1/search",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "filter": {"property": "object", "value": "database"},
                "page_size": 50,
            },
        )
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="notion_request_failed")
        payload = response.json()

    databases = []
    for item in payload.get("results", []):
        db_id = item.get("id", "")
        if not db_id:
            continue
        title_parts = item.get("title") or []
        title = ""
        if title_parts:
            title = title_parts[0].get("plain_text", "")
        if not title:
            props = item.get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title = prop.get("title", [{}])[0].get("plain_text", "")
                    break
        databases.append({"id": db_id, "name": title or db_id})
    return databases


def disconnect_integration(db: Session, provider: str) -> None:
    delete_integration(db, provider)


def integrations_overview(db: Session) -> dict[str, Any]:
    settings = get_settings()
    from .integration_store import integration_status

    return {
        "microsoft": {
            **integration_status(db, "microsoft"),
            "oauth_available": settings.entra_configured,
        },
        "notion": {
            **integration_status(db, "notion"),
            "oauth_available": settings.notion_oauth_configured,
        },
    }
