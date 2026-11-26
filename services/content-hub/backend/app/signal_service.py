from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .user_integration_store import (
    delete_user_integration,
    get_user_integration,
    read_user_access_token,
    save_user_integration,
    user_integration_status,
)

logger = logging.getLogger(__name__)

# signal-cli-rest-api (https://github.com/bbernhard/signal-cli-rest-api) is an
# unofficial, community-maintained wrapper around signal-cli. Signal itself has
# no public OAuth/API, so "connecting" an account means linking it as a
# secondary device (QR code, scanned from the Signal app) against this
# self-hosted sidecar - see services/signal-cli-rest-api/.


def _signal_base_url() -> str:
    url = get_settings().signal_cli_rest_api_url.strip()
    return url.rstrip("/")


def signal_configured() -> bool:
    return bool(_signal_base_url())


async def signal_service_reachable() -> bool:
    base = _signal_base_url()
    if not base:
        return False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base}/v1/health")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _list_linked_accounts() -> list[str]:
    base = _signal_base_url()
    if not base:
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{base}/v1/accounts")
        if response.status_code != 200:
            return []
        payload = response.json()
        return [str(number) for number in payload] if isinstance(payload, list) else []


def signal_status(db: Session, *, user_id: str) -> dict[str, Any]:
    return {
        **user_integration_status(db, user_id=user_id, provider="signal"),
        "service_configured": signal_configured(),
    }


async def start_signal_link(*, device_name: str) -> dict[str, Any]:
    """Begin linking a Signal account: returns a QR code (as a data URL) to
    scan from Signal > Settings > Linked devices > Link new device, plus the
    accounts snapshot taken just before, needed later to detect which number
    got linked."""
    base = _signal_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="signal_not_configured")

    before = await _list_linked_accounts()

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            f"{base}/v1/qrcodelink",
            params={"device_name": device_name or "elphen"},
        )
        if response.status_code != 200:
            logger.warning("Signal qrcodelink failed: %s", response.text)
            raise HTTPException(status_code=502, detail="signal_link_failed")
        qr_bytes = response.content

    qr_data_url = "data:image/png;base64," + base64.b64encode(qr_bytes).decode("ascii")
    return {"qr_data_url": qr_data_url, "accounts_before": before}


async def complete_signal_link(
    db: Session,
    *,
    user_id: str,
    accounts_before: list[str],
) -> dict[str, Any]:
    """Poll this after start_signal_link(): once the phone has scanned the QR
    code, the newly linked number appears in /v1/accounts."""
    after = await _list_linked_accounts()
    new_numbers = [number for number in after if number not in set(accounts_before)]
    if not new_numbers:
        return {"connected": False}

    number = new_numbers[0]
    save_user_integration(
        db,
        user_id=user_id,
        provider="signal",
        access_token=number,
        account_label=number,
        calendar_enabled=False,
        mail_enabled=True,
    )
    return {"connected": True, "account": number}


def _require_signal_number(db: Session, *, user_id: str) -> str:
    row = get_user_integration(db, user_id=user_id, provider="signal")
    if not row:
        raise HTTPException(status_code=400, detail="signal_not_connected")
    number = read_user_access_token(row)
    if not number:
        raise HTTPException(status_code=400, detail="signal_not_connected")
    return number


async def disconnect_signal(db: Session, *, user_id: str) -> None:
    base = _signal_base_url()
    row = get_user_integration(db, user_id=user_id, provider="signal")
    if row and base:
        number = read_user_access_token(row)
        if number:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.delete(f"{base}/v1/accounts/{number}")
            except httpx.HTTPError:
                logger.warning("Signal account unregister failed for %s", number)
    delete_user_integration(db, user_id=user_id, provider="signal")


def _parse_envelope(entry: dict[str, Any]) -> dict[str, Any] | None:
    envelope = entry.get("envelope") if isinstance(entry, dict) else None
    if not isinstance(envelope, dict):
        return None
    data_message = envelope.get("dataMessage")
    if not isinstance(data_message, dict):
        return None
    text = str(data_message.get("message") or "").strip()
    if not text:
        return None
    timestamp_ms = data_message.get("timestamp") or envelope.get("timestamp")
    received_at = None
    if isinstance(timestamp_ms, (int, float)):
        received_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).isoformat()
    sender_number = str(envelope.get("sourceNumber") or envelope.get("source") or "")
    sender_name = str(envelope.get("sourceName") or "")
    return {
        "id": f"{sender_number}-{timestamp_ms}",
        "from_number": sender_number,
        "from_name": sender_name or sender_number,
        "text": text,
        "received_at": received_at,
    }


async def fetch_signal_messages(db: Session, *, user_id: str) -> list[dict[str, Any]]:
    base = _signal_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="signal_not_configured")
    number = _require_signal_number(db, user_id=user_id)

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{base}/v1/receive/{number}")
        if response.status_code != 200:
            logger.warning("Signal receive failed: %s", response.text)
            raise HTTPException(status_code=502, detail="signal_receive_failed")
        payload = response.json()

    messages = []
    for entry in payload if isinstance(payload, list) else []:
        parsed = _parse_envelope(entry)
        if parsed:
            messages.append(parsed)
    messages.sort(key=lambda item: item.get("received_at") or "", reverse=True)
    return messages


async def send_signal_message(db: Session, *, user_id: str, to_number: str, text: str) -> None:
    base = _signal_base_url()
    if not base:
        raise HTTPException(status_code=400, detail="signal_not_configured")
    number = _require_signal_number(db, user_id=user_id)

    recipient = (to_number or "").strip()
    message = (text or "").strip()
    if not recipient or not message:
        raise HTTPException(status_code=400, detail="validation")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{base}/v2/send",
            json={"message": message, "number": number, "recipients": [recipient]},
        )
        if response.status_code not in (200, 201):
            logger.warning("Signal send failed: %s", response.text)
            raise HTTPException(status_code=502, detail="signal_send_failed")
