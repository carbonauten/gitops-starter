from __future__ import annotations

import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from .config import Settings, get_settings
from .i18n import normalize_language, translate

SESSION_COOKIE = "content_hub_session"


def _serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret, salt="content-hub-session")


def get_session(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        data = _serializer(get_settings()).loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data


def set_session(response: Response, data: dict[str, Any]) -> None:
    settings = get_settings()
    token = _serializer(settings).dumps(data)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.effective_redirect_uri.startswith("https://"),
        samesite="lax",
        max_age=settings.session_max_age,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def require_user(request: Request) -> dict[str, Any]:
    session = get_session(request)
    if not session or "user" not in session:
        raise HTTPException(status_code=401, detail="unauthorized")
    return session["user"]


def entra_authorize_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    params = {
        "client_id": settings.azure_client_id,
        "response_type": "code",
        "redirect_uri": settings.effective_redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email User.Read offline_access",
        "state": state,
    }
    return (
        f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/authorize?"
        f"{urlencode(params)}"
    )


async def exchange_code_for_user(code: str, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    token_url = f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": settings.azure_client_id,
        "client_secret": settings.azure_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.effective_redirect_uri,
        "scope": "openid profile email User.Read offline_access",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(token_url, data=data)
        if token_response.status_code != 200:
            raise HTTPException(status_code=502, detail="token_exchange_failed")

        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="token_exchange_failed")

        profile_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_response.status_code != 200:
            raise HTTPException(status_code=502, detail="profile_fetch_failed")

        profile = profile_response.json()

    display_name = profile.get("displayName") or profile.get("userPrincipalName") or "User"
    email = profile.get("mail") or profile.get("userPrincipalName") or ""

    return {
        "id": profile.get("id", ""),
        "name": display_name,
        "email": email,
        "language": get_settings().default_language,
    }


def mock_user(language: str | None = None) -> dict[str, Any]:
    return {
        "id": "mock-user-001",
        "name": "Demo User",
        "email": "demo@example.com",
        "language": normalize_language(language),
    }


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)
