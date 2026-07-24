from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .user_integration_store import (
    delete_user_integration,
    get_user_integration,
    read_user_access_token,
    read_user_refresh_token,
    save_user_integration,
    user_integration_status,
)

logger = logging.getLogger(__name__)

# Personal Microsoft 365: calendar, mailbox, and OneDrive for the signed-in user.
OUTLOOK_USER_SCOPES = (
    "offline_access User.Read Calendars.ReadWrite Mail.ReadWrite Files.Read"
)


def outlook_redirect_uri(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    origin = settings.effective_public_origin or "http://localhost:8080"
    return f"{origin.rstrip('/')}/api/integrations/outlook/callback"


def outlook_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not settings.entra_configured:
        raise HTTPException(status_code=400, detail="microsoft_auth_unavailable")
    params = {
        "client_id": settings.azure_client_id,
        "response_type": "code",
        "redirect_uri": outlook_redirect_uri(settings),
        "response_mode": "query",
        "scope": OUTLOOK_USER_SCOPES,
        "state": state,
        "prompt": "consent",
    }
    return (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/authorize?"
        f"{urlencode(params)}"
    )


def _expires_at_from_payload(payload: dict[str, Any]) -> datetime | None:
    expires_in = payload.get("expires_in")
    if not expires_in:
        return None
    try:
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in) - 60)
    except (TypeError, ValueError):
        return None


async def _exchange_outlook_code(code: str, settings: Settings) -> dict[str, Any]:
    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": outlook_redirect_uri(settings),
        "scope": OUTLOOK_USER_SCOPES,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            logger.error("Outlook user token failed: %s", response.text)
            raise HTTPException(status_code=502, detail="integration_token_failed")
        return response.json()


async def complete_outlook_connection(
    db: Session,
    *,
    code: str,
    user: dict,
) -> dict[str, Any]:
    settings = get_settings()
    user_id = user.get("db_id") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthorized")

    payload = await _exchange_outlook_code(code, settings)
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
    display_name = profile.get("displayName") or email

    save_user_integration(
        db,
        user_id=user_id,
        provider="outlook",
        access_token=access_token,
        refresh_token=payload.get("refresh_token", ""),
        expires_at=_expires_at_from_payload(payload),
        account_label=email or display_name,
        calendar_enabled=True,
        mail_enabled=True,
    )

    return {
        "provider": "outlook",
        "account": email or display_name,
        "calendar_enabled": True,
        "mail_enabled": True,
    }


async def refresh_outlook_access_token(db: Session, *, user_id: str) -> str:
    row = get_user_integration(db, user_id=user_id, provider="outlook")
    if not row:
        raise HTTPException(status_code=400, detail="outlook_not_connected")

    access_token = read_user_access_token(row)
    if row.expires_at and row.expires_at > datetime.now(timezone.utc) and access_token:
        return access_token

    refresh_token = read_user_refresh_token(row)
    if not refresh_token:
        return access_token

    settings = get_settings()
    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": OUTLOOK_USER_SCOPES,
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(token_url, data=data)
        if response.status_code != 200:
            logger.error("Outlook token refresh failed: %s", response.text)
            raise HTTPException(status_code=502, detail="integration_token_failed")
        payload = response.json()

    new_access = payload.get("access_token", "")
    if not new_access:
        raise HTTPException(status_code=502, detail="integration_token_failed")

    save_user_integration(
        db,
        user_id=user_id,
        provider="outlook",
        access_token=new_access,
        refresh_token=payload.get("refresh_token", refresh_token),
        expires_at=_expires_at_from_payload(payload),
        account_label=row.account_label,
        calendar_enabled=row.calendar_enabled,
        mail_enabled=row.mail_enabled,
    )
    return new_access


async def get_outlook_access_token(db: Session, *, user_id: str) -> str | None:
    row = get_user_integration(db, user_id=user_id, provider="outlook")
    if not row:
        return None
    return await refresh_outlook_access_token(db, user_id=user_id)


def disconnect_outlook(db: Session, *, user_id: str) -> None:
    delete_user_integration(db, user_id=user_id, provider="outlook")


def outlook_status(db: Session, *, user_id: str) -> dict[str, Any]:
    settings = get_settings()
    return {
        **user_integration_status(db, user_id=user_id, provider="outlook"),
        "oauth_available": settings.entra_configured,
    }


def _parse_graph_datetime(value: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    raw = value.get("dateTime") or ""
    if not raw:
        return None, None
    # Graph returns local or UTC; take date part and keep ISO-ish datetime.
    date_part = raw[:10]
    try:
        # Normalize to ISO with Z when possible
        cleaned = raw.replace("Z", "+00:00")
        if "." in cleaned:
            head, rest = cleaned.split(".", 1)
            tz = ""
            for sep in ("+", "-"):
                if sep in rest[1:] or rest.startswith("+") or (rest.startswith("-") and "T" not in rest):
                    idx = rest.find("+") if "+" in rest else rest.rfind("-")
                    if idx > 0:
                        tz = rest[idx:]
                        rest = rest[:idx]
                        break
            cleaned = f"{head}{tz}" if tz else head
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return date_part, dt.isoformat()
    except ValueError:
        return date_part, raw


async def fetch_outlook_calendar_events(
    db: Session,
    *,
    user_id: str,
    days_ahead: int = 90,
    days_back: int = 14,
) -> list[dict[str, Any]]:
    row = get_user_integration(db, user_id=user_id, provider="outlook")
    if not row or not row.calendar_enabled:
        return []

    token = await get_outlook_access_token(db, user_id=user_id)
    if not token:
        return []

    today = date.today()
    start = datetime.combine(today - timedelta(days=days_back), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(today + timedelta(days=days_ahead), datetime.max.time(), tzinfo=timezone.utc)

    params = {
        "startDateTime": start.isoformat().replace("+00:00", "Z"),
        "endDateTime": end.isoformat().replace("+00:00", "Z"),
        "$select": "id,subject,start,end,webLink,isAllDay,location",
        "$orderby": "start/dateTime",
        "$top": "100",
    }
    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/calendarView",
            headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'},
            params=params,
        )
        if response.status_code != 200:
            logger.warning("Outlook calendarView failed: %s", response.text)
            return []
        payload = response.json()

    for item in payload.get("value", []):
        event_id = item.get("id") or ""
        event_date, event_dt = _parse_graph_datetime(item.get("start"))
        if not event_date:
            continue
        location = ""
        loc = item.get("location") or {}
        if isinstance(loc, dict):
            location = loc.get("displayName") or ""
        events.append(
            {
                "id": f"outlook-{event_id}",
                "type": "outlook_event",
                "title": item.get("subject") or "(ohne Titel)",
                "date": event_date,
                "datetime": event_dt,
                "resource_type": "outlook",
                "resource_id": event_id,
                "status": "outlook",
                "external_url": item.get("webLink") or "",
                "location": location,
            }
        )
    return events
