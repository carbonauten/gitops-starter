from __future__ import annotations

import logging
import secrets
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request, Response
from itsdangerous import BadSignature, URLSafeSerializer

from .config import Settings, get_settings
from .i18n import normalize_language, translate

logger = logging.getLogger(__name__)

SESSION_COOKIE = "content_hub_session"
SHOP_SESSION_COOKIE = "fuckco2_shop_session"

# GroupMember.Read.All lets a signed-in user's own group memberships be read
# (via /me/memberOf) for Entra-group-to-role mapping; it does not grant access
# to other users' data.
ENTRA_LOGIN_SCOPE = "openid profile email User.Read GroupMember.Read.All offline_access"


def _serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret, salt="content-hub-session")


def _shop_serializer(settings: Settings) -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret, salt="fuckco2-shop-session")


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
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age,
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


def get_shop_session(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SHOP_SESSION_COOKIE)
    if not token:
        return None
    try:
        data = _shop_serializer(get_settings()).loads(token)
    except BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    return data


def set_shop_session(response: Response, data: dict[str, Any]) -> None:
    settings = get_settings()
    token = _shop_serializer(settings).dumps(data)
    response.set_cookie(
        SHOP_SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_max_age,
    )


def clear_shop_session(response: Response) -> None:
    response.delete_cookie(SHOP_SESSION_COOKIE)


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
        "scope": ENTRA_LOGIN_SCOPE,
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
        "scope": ENTRA_LOGIN_SCOPE,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        token_response = await client.post(token_url, data=data)
        if token_response.status_code != 200:
            raise HTTPException(status_code=502, detail="token_exchange_failed")

        token_payload = token_response.json()
        access_token = token_payload.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="token_exchange_failed")

        headers = {"Authorization": f"Bearer {access_token}"}
        profile_response = await client.get("https://graph.microsoft.com/v1.0/me", headers=headers)
        if profile_response.status_code != 200:
            raise HTTPException(status_code=502, detail="profile_fetch_failed")

        profile = profile_response.json()
        group_ids = await _fetch_member_group_ids(client, headers)

    display_name = profile.get("displayName") or profile.get("userPrincipalName") or "User"
    email = profile.get("mail") or profile.get("userPrincipalName") or ""

    return {
        "id": profile.get("id", ""),
        "name": display_name,
        "email": email,
        "language": get_settings().default_language,
        "group_ids": group_ids,
    }


async def _fetch_member_group_ids(client: httpx.AsyncClient, headers: dict[str, str]) -> list[str]:
    """Best-effort read of the signed-in user's Entra group ids for role mapping.

    Not fatal when it fails (missing consent, conditional access, throttling) —
    the user still logs in, just without group-based role sync for this session.
    """
    try:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/memberOf?$select=id",
            headers=headers,
        )
        if response.status_code != 200:
            logger.warning("memberOf lookup failed: %s %s", response.status_code, response.text[:300])
            return []
        payload = response.json()
        return [str(item["id"]) for item in payload.get("value") or [] if item.get("id")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("memberOf lookup errored: %s", exc)
        return []


def mock_user(language: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    email = settings.mock_user_email.strip().lower() or "demo@example.com"
    name = settings.mock_user_name.strip() or email.split("@", 1)[0].replace(".", " ").title()
    return {
        "id": "mock-user-001",
        "name": name,
        "email": email,
        "language": normalize_language(language),
    }


def new_oauth_state() -> str:
    return secrets.token_urlsafe(24)
