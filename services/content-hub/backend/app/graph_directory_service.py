"""Microsoft 365 / Entra user directory for IT masters.

Uses Graph application permissions when Entra is configured. Falls back to an
in-memory carbonauten sample directory when Graph is unavailable (local/tests).
Does not bypass admin consent or user login.
"""

from __future__ import annotations

import copy
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException

from .config import Settings, get_settings
from .graph_client import get_app_access_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
USER_SELECT = (
    "id,displayName,givenName,surname,userPrincipalName,mail,jobTitle,department,"
    "accountEnabled,userType,createdDateTime,assignedLicenses,usageLocation"
)

_SEED_USERS: list[dict[str, Any]] = [
    {
        "id": "m365-mike-mueller",
        "display_name": "Mike Müller",
        "user_principal_name": "mike.mueller@carbonauten.com",
        "mail": "mike.mueller@carbonauten.com",
        "job_title": "IT Administrator",
        "department": "IT",
        "account_enabled": True,
        "user_type": "Member",
        "licenses": ["Microsoft 365 Business Premium"],
        "usage_location": "DE",
        "created_at": "2022-03-01T08:00:00+00:00",
    },
    {
        "id": "m365-torsten-becker",
        "display_name": "Torsten Becker",
        "user_principal_name": "torsten.becker@carbonauten.com",
        "mail": "torsten.becker@carbonauten.com",
        "job_title": "CEO",
        "department": "Management",
        "account_enabled": True,
        "user_type": "Member",
        "licenses": ["Microsoft 365 Business Premium"],
        "usage_location": "DE",
        "created_at": "2018-06-01T08:00:00+00:00",
    },
    {
        "id": "m365-redaktion",
        "display_name": "Redaktion Carbonauten",
        "user_principal_name": "redaktion@carbonauten.com",
        "mail": "redaktion@carbonauten.com",
        "job_title": "Editor",
        "department": "Kommunikation",
        "account_enabled": True,
        "user_type": "Member",
        "licenses": ["Microsoft 365 Business Standard"],
        "usage_location": "DE",
        "created_at": "2023-01-12T08:00:00+00:00",
    },
    {
        "id": "m365-guest-chibi",
        "display_name": "Chibi Factory Guest",
        "user_principal_name": "chibi.guest@carbonauten.com",
        "mail": "chibi.guest@carbonauten.com",
        "job_title": "External",
        "department": "China",
        "account_enabled": False,
        "user_type": "Guest",
        "licenses": [],
        "usage_location": "CN",
        "created_at": "2023-11-07T08:00:00+00:00",
    },
]

_mock_users: list[dict[str, Any]] = []


def reset_mock_directory() -> None:
    global _mock_users
    _mock_users = copy.deepcopy(_SEED_USERS)


reset_mock_directory()


def directory_uses_mock(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if getattr(settings, "m365_directory_mock_mode", False):
        return True
    return not settings.entra_configured


def generate_temporary_password() -> str:
    return f"Ca-{secrets.token_urlsafe(10)}!1A"


def directory_status(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    mock = directory_uses_mock(settings)
    return {
        "mock": mock,
        "graph_configured": settings.entra_configured,
        "permissions": [
            "User.Read.All",
            "User.ReadWrite.All",
            "Directory.Read.All",
            "Organization.Read.All",
        ],
    }


def user_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id") or "",
        "display_name": row.get("display_name") or "",
        "user_principal_name": row.get("user_principal_name") or "",
        "mail": row.get("mail") or row.get("user_principal_name") or "",
        "job_title": row.get("job_title") or "",
        "department": row.get("department") or "",
        "account_enabled": bool(row.get("account_enabled", True)),
        "user_type": row.get("user_type") or "Member",
        "licenses": list(row.get("licenses") or []),
        "usage_location": row.get("usage_location") or "",
        "created_at": row.get("created_at"),
    }


def _graph_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "ConsistencyLevel": "eventual",
    }


async def _graph_json(
    method: str,
    path: str,
    *,
    token: str,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = path if path.startswith("http") else f"{GRAPH_BASE}{path}"
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.request(
            method,
            url,
            headers=_graph_headers(token),
            params=params,
            json=json_body,
        )
    if response.status_code >= 400:
        logger.error("Graph directory %s %s failed: %s", method, path, response.text[:800])
        if response.status_code in {401, 403}:
            raise HTTPException(status_code=502, detail="graph_directory_forbidden")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="not_found")
        if response.status_code == 409:
            raise HTTPException(status_code=409, detail="user_exists")
        raise HTTPException(status_code=502, detail="graph_directory_failed")
    if not response.content:
        return {}
    return response.json()


async def _sku_map(token: str) -> dict[str, str]:
    payload = await _graph_json("GET", "/subscribedSkus", token=token)
    mapping: dict[str, str] = {}
    for item in payload.get("value") or []:
        sku_id = str(item.get("skuId") or "")
        part = str(item.get("skuPartNumber") or sku_id)
        if sku_id:
            mapping[sku_id] = part.replace("_", " ")
    return mapping


def _from_graph_user(item: dict[str, Any], skus: dict[str, str]) -> dict[str, Any]:
    licenses = []
    for assignment in item.get("assignedLicenses") or []:
        sku_id = str(assignment.get("skuId") or "")
        if sku_id:
            licenses.append(skus.get(sku_id) or sku_id)
    created = item.get("createdDateTime")
    return user_to_dict(
        {
            "id": item.get("id") or "",
            "display_name": item.get("displayName") or "",
            "user_principal_name": item.get("userPrincipalName") or "",
            "mail": item.get("mail") or item.get("userPrincipalName") or "",
            "job_title": item.get("jobTitle") or "",
            "department": item.get("department") or "",
            "account_enabled": bool(item.get("accountEnabled", True)),
            "user_type": item.get("userType") or "Member",
            "licenses": licenses,
            "usage_location": item.get("usageLocation") or "",
            "created_at": created,
        }
    )


def _filter_users(rows: list[dict[str, Any]], query: str = "") -> list[dict[str, Any]]:
    needle = (query or "").strip().lower()
    if not needle:
        return rows
    matched = []
    for row in rows:
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("display_name", "user_principal_name", "mail", "job_title", "department")
        ).lower()
        if needle in blob:
            matched.append(row)
    return matched


async def list_directory_users(*, query: str = "", settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    if directory_uses_mock(settings):
        rows = [user_to_dict(item) for item in _mock_users]
        return _filter_users(rows, query)
    token = await get_app_access_token(settings)
    skus = await _sku_map(token)
    params = {"$select": USER_SELECT, "$top": "999", "$orderby": "displayName"}
    payload = await _graph_json("GET", "/users", token=token, params=params)
    rows = [_from_graph_user(item, skus) for item in payload.get("value") or []]
    return _filter_users(rows, query)


async def get_directory_user(user_id: str, *, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    if directory_uses_mock(settings):
        for item in _mock_users:
            if item["id"] == user_id or item["user_principal_name"].lower() == user_id.lower():
                return user_to_dict(item)
        raise HTTPException(status_code=404, detail="not_found")
    token = await get_app_access_token(settings)
    skus = await _sku_map(token)
    item = await _graph_json("GET", f"/users/{user_id}", token=token, params={"$select": USER_SELECT})
    return _from_graph_user(item, skus)


def _default_domain(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    emails = list(settings.it_admin_emails_list)
    if emails and "@" in emails[0]:
        return emails[0].split("@", 1)[1]
    return "carbonauten.com"


def _normalize_upn(value: str, *, settings: Settings | None = None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        raise HTTPException(status_code=400, detail="validation_error")
    if "@" not in raw:
        raw = f"{raw}@{_default_domain(settings)}"
    return raw


async def create_directory_user(
    *,
    display_name: str,
    user_principal_name: str,
    password: str | None = None,
    job_title: str = "",
    department: str = "",
    usage_location: str = "DE",
    settings: Settings | None = None,
) -> tuple[dict[str, Any], str]:
    settings = settings or get_settings()
    name = (display_name or "").strip()
    upn = _normalize_upn(user_principal_name, settings=settings)
    if not name:
        raise HTTPException(status_code=400, detail="validation_error")
    temp_password = password.strip() if password and password.strip() else generate_temporary_password()
    nickname = upn.split("@", 1)[0][:64]
    if directory_uses_mock(settings):
        if any(item["user_principal_name"].lower() == upn for item in _mock_users):
            raise HTTPException(status_code=409, detail="user_exists")
        row = {
            "id": f"m365-{uuid4()}",
            "display_name": name,
            "user_principal_name": upn,
            "mail": upn,
            "job_title": job_title.strip(),
            "department": department.strip(),
            "account_enabled": True,
            "user_type": "Member",
            "licenses": [],
            "usage_location": usage_location or "DE",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _mock_users.append(row)
        return user_to_dict(row), temp_password

    token = await get_app_access_token(settings)
    body: dict[str, Any] = {
        "accountEnabled": True,
        "displayName": name,
        "mailNickname": re.sub(r"[^a-z0-9._-]+", "", nickname) or "user",
        "userPrincipalName": upn,
        "usageLocation": (usage_location or "DE")[:2].upper(),
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": temp_password,
        },
    }
    if job_title.strip():
        body["jobTitle"] = job_title.strip()
    if department.strip():
        body["department"] = department.strip()
    payload = await _graph_json("POST", "/users", token=token, json_body=body)
    created = await get_directory_user(str(payload.get("id") or upn), settings=settings)
    return created, temp_password


async def set_directory_user_enabled(
    user_id: str,
    enabled: bool,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if directory_uses_mock(settings):
        for item in _mock_users:
            if item["id"] == user_id or item["user_principal_name"].lower() == user_id.lower():
                item["account_enabled"] = bool(enabled)
                return user_to_dict(item)
        raise HTTPException(status_code=404, detail="not_found")
    token = await get_app_access_token(settings)
    await _graph_json("PATCH", f"/users/{user_id}", token=token, json_body={"accountEnabled": bool(enabled)})
    return await get_directory_user(user_id, settings=settings)


async def reset_directory_password(
    user_id: str,
    *,
    password: str | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], str]:
    settings = settings or get_settings()
    temp_password = password.strip() if password and password.strip() else generate_temporary_password()
    if directory_uses_mock(settings):
        user = await get_directory_user(user_id, settings=settings)
        return user, temp_password
    token = await get_app_access_token(settings)
    await _graph_json(
        "PATCH",
        f"/users/{user_id}",
        token=token,
        json_body={
            "passwordProfile": {
                "forceChangePasswordNextSignIn": True,
                "password": temp_password,
            }
        },
    )
    user = await get_directory_user(user_id, settings=settings)
    return user, temp_password


def find_user_in_list(rows: list[dict[str, Any]], needle: str) -> dict[str, Any] | None:
    value = (needle or "").strip().lower()
    if not value:
        return None
    for row in rows:
        if row["id"].lower() == value:
            return row
        if row["user_principal_name"].lower() == value:
            return row
        if (row.get("mail") or "").lower() == value:
            return row
        if row["display_name"].lower() == value:
            return row
    for row in rows:
        if value in row["display_name"].lower() or value in row["user_principal_name"].lower():
            return row
    return None
