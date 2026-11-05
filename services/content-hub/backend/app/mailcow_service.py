"""Self-hosted Mailcow mail server integration for IT masters.

Talks to a Mailcow instance's REST API (see infra/mailcow/README.md for how to
deploy one) to list/create/delete real mailboxes. Falls back to an in-memory
sample mailbox list when Mailcow isn't configured (local/dev/tests), the same
pattern used for the M365 directory in graph_directory_service.py.

Note: this wraps Mailcow's documented REST API conventions (X-API-Key header,
/api/v1/<action>/<object> paths) but has not been exercised against a live
Mailcow instance - verify against your real deployment once it's up, since
Mailcow doesn't publish a versioned API contract.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .mailcow_config_service import MailcowCredentials, resolve_mailcow_credentials

logger = logging.getLogger(__name__)

_SEED_MAILBOXES: list[dict[str, Any]] = [
    {
        "email": "info@carbonauten.com",
        "local_part": "info",
        "domain": "carbonauten.com",
        "display_name": "Info",
        "quota_mb": 3072,
        "active": True,
    },
    {
        "email": "support@fuckco2.shop",
        "local_part": "support",
        "domain": "fuckco2.shop",
        "display_name": "Support",
        "quota_mb": 3072,
        "active": True,
    },
]

_mock_mailboxes: list[dict[str, Any]] = []


def reset_mock_mailboxes() -> None:
    global _mock_mailboxes
    _mock_mailboxes = copy.deepcopy(_SEED_MAILBOXES)


reset_mock_mailboxes()


def mailcow_uses_mock(db: Session | None = None) -> bool:
    return not resolve_mailcow_credentials(db).configured


def mailcow_status(db: Session) -> dict[str, Any]:
    from .mailcow_config_service import mailcow_status as _status

    payload = _status(db)
    payload["mock"] = mailcow_uses_mock(db)
    return payload


def _client(creds: MailcowCredentials) -> httpx.Client:
    return httpx.Client(
        base_url=creds.api_url,
        headers={"X-API-Key": creds.api_key, "Content-Type": "application/json"},
        timeout=20.0,
    )


def _request_failed(payload: Any) -> bool:
    """Mailcow responses are usually a list of {type, msg} objects; "error" means failure."""
    items = payload if isinstance(payload, list) else [payload]
    return any(isinstance(item, dict) and item.get("type") == "error" for item in items)


def list_mailboxes(db: Session, *, domain: str = "") -> list[dict[str, Any]]:
    creds = resolve_mailcow_credentials(db)
    target_domain = (domain or creds.default_domain).strip()

    if not creds.configured:
        boxes = _mock_mailboxes
        if target_domain:
            boxes = [box for box in boxes if box["domain"] == target_domain]
        return boxes

    if not target_domain:
        raise HTTPException(status_code=400, detail="mailcow_domain_required")

    with _client(creds) as client:
        response = client.get(f"/api/v1/get/mailbox/all/{target_domain}")
        if response.status_code != 200:
            logger.warning("Mailcow list mailboxes failed: %s", response.text)
            raise HTTPException(status_code=502, detail="mailcow_request_failed")
        payload = response.json()

    if not isinstance(payload, list):
        return []
    return [
        {
            "email": entry.get("username", ""),
            "local_part": entry.get("local_part", ""),
            "domain": entry.get("domain", target_domain),
            "display_name": entry.get("name", ""),
            "quota_mb": int(entry.get("quota", 0) or 0) // (1024 * 1024) if entry.get("quota") else 0,
            "active": str(entry.get("active", "1")) == "1",
        }
        for entry in payload
        if isinstance(entry, dict)
    ]


def create_mailbox(
    db: Session,
    *,
    local_part: str,
    domain: str,
    display_name: str,
    password: str,
    quota_mb: int = 3072,
) -> dict[str, Any]:
    creds = resolve_mailcow_credentials(db)
    local = local_part.strip().lower()
    target_domain = (domain or creds.default_domain).strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", local):
        raise HTTPException(status_code=400, detail="mailcow_invalid_local_part")
    if not target_domain:
        raise HTTPException(status_code=400, detail="mailcow_domain_required")
    email = f"{local}@{target_domain}"

    if not creds.configured:
        if any(box["email"] == email for box in _mock_mailboxes):
            raise HTTPException(status_code=409, detail="mailcow_already_exists")
        entry = {
            "email": email,
            "local_part": local,
            "domain": target_domain,
            "display_name": display_name or local,
            "quota_mb": quota_mb,
            "active": True,
        }
        _mock_mailboxes.append(entry)
        return entry

    with _client(creds) as client:
        response = client.post(
            "/api/v1/add/mailbox",
            json={
                "local_part": local,
                "domain": target_domain,
                "name": display_name or local,
                "quota": str(quota_mb),
                "password": password,
                "password2": password,
                "active": "1",
                "force_pw_update": "0",
                "tls_enforce_in": "1",
                "tls_enforce_out": "1",
            },
        )
        if response.status_code != 200:
            logger.warning("Mailcow create mailbox failed: %s", response.text)
            raise HTTPException(status_code=502, detail="mailcow_request_failed")
        payload = response.json()
        if _request_failed(payload):
            logger.warning("Mailcow rejected mailbox creation: %s", payload)
            raise HTTPException(status_code=400, detail="mailcow_request_rejected")

    return {
        "email": email,
        "local_part": local,
        "domain": target_domain,
        "display_name": display_name or local,
        "quota_mb": quota_mb,
        "active": True,
    }


def delete_mailbox(db: Session, *, email: str) -> None:
    creds = resolve_mailcow_credentials(db)

    if not creds.configured:
        global _mock_mailboxes
        remaining = [box for box in _mock_mailboxes if box["email"] != email]
        if len(remaining) == len(_mock_mailboxes):
            raise HTTPException(status_code=404, detail="not_found")
        _mock_mailboxes = remaining
        return

    with _client(creds) as client:
        response = client.post("/api/v1/delete/mailbox", json=[email])
        if response.status_code != 200:
            logger.warning("Mailcow delete mailbox failed: %s", response.text)
            raise HTTPException(status_code=502, detail="mailcow_request_failed")
        payload = response.json()
        if _request_failed(payload):
            logger.warning("Mailcow rejected mailbox deletion: %s", payload)
            raise HTTPException(status_code=404, detail="not_found")
