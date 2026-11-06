"""Generic IMAP mailbox integration (e.g. for Strato-hosted mailboxes).

Unlike the Outlook integration (OAuth2 against Microsoft Graph), this talks
directly to any standard IMAP server using basic auth - host/port/username/
password configured per-account by an IT-Master (see imap_config_service.py).
Providers like Strato publish no REST API for mailbox access, only IMAP/SMTP,
so this is the only way to surface those mailboxes inside the platform.

Note: written against Python's stdlib imaplib/email per the IMAP4rev1 spec,
but has not been exercised against a live Strato (or any other) mailbox -
verify against your real account before relying on it in production.
"""

from __future__ import annotations

import email
import email.policy
import imaplib
import logging
from datetime import timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .imap_config_service import ImapCredentials, get_imap_credentials

logger = logging.getLogger(__name__)


def _connect(creds: ImapCredentials) -> imaplib.IMAP4:
    try:
        conn: imaplib.IMAP4 = (
            imaplib.IMAP4_SSL(creds.host, creds.port) if creds.use_ssl else imaplib.IMAP4(creds.host, creds.port)
        )
    except OSError as exc:
        logger.warning("IMAP connect failed for %s:%s: %s", creds.host, creds.port, exc)
        raise HTTPException(status_code=502, detail="imap_connect_failed") from exc

    try:
        conn.login(creds.username, creds.password)
    except imaplib.IMAP4.error as exc:
        logger.warning("IMAP login failed for %s on %s: %s", creds.username, creds.host, exc)
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 - best-effort cleanup after a failed login
            pass
        raise HTTPException(status_code=502, detail="imap_login_failed") from exc
    return conn


def _disconnect(conn: imaplib.IMAP4) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001 - best-effort cleanup, connection may already be unusable
        pass
    try:
        conn.logout()
    except Exception:  # noqa: BLE001
        pass


def _select_folder(conn: imaplib.IMAP4, folder: str) -> None:
    status, _ = conn.select(folder, readonly=True)
    if status != "OK":
        raise HTTPException(status_code=502, detail="imap_folder_not_found")


def _header_value(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _parse_person(raw: str) -> dict[str, str]:
    name, addr = parseaddr(raw or "")
    return {"name": (name or "").strip(), "email": (addr or "").strip()}


def _parse_people(values: list[str] | None) -> list[dict[str, str]]:
    return [{"name": (name or "").strip(), "email": (addr or "").strip()} for name, addr in getaddresses(values or [])]


def _parse_date(raw: str) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def list_messages(db: Session, *, account_id: str, limit: int = 30) -> list[dict[str, Any]]:
    creds = get_imap_credentials(db, account_id)
    conn = _connect(creds)
    try:
        _select_folder(conn, creds.folder)
        status, data = conn.uid("search", None, "ALL")
        if status != "OK":
            raise HTTPException(status_code=502, detail="imap_search_failed")
        uids = data[0].split() if data and data[0] else []
        uids = uids[-max(1, min(limit, 100)) :]
        uids.reverse()  # most recent first

        messages: list[dict[str, Any]] = []
        for uid in uids:
            status, msg_data = conn.uid("fetch", uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            meta_raw, header_raw = msg_data[0]
            flags = imaplib.ParseFlags(meta_raw) if meta_raw else ()
            header = email.message_from_bytes(header_raw, policy=email.policy.default)
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            messages.append(
                {
                    "id": uid_str,
                    "subject": _header_value(header.get("subject")) or "(ohne Betreff)",
                    "from": _parse_person(_header_value(header.get("from"))),
                    "received_at": _parse_date(_header_value(header.get("date"))),
                    "preview": "",
                    "is_read": b"\\Seen" in flags,
                    # Detecting attachments cheaply would need a BODYSTRUCTURE fetch per
                    # message; left out of this first version, see ROADMAP.md.
                    "has_attachments": False,
                }
            )
        return messages
    finally:
        _disconnect(conn)


def get_message(db: Session, *, account_id: str, message_id: str) -> dict[str, Any]:
    creds = get_imap_credentials(db, account_id)
    conn = _connect(creds)
    try:
        _select_folder(conn, creds.folder)
        uid = message_id.encode()
        status, msg_data = conn.uid("fetch", uid, "(FLAGS BODY.PEEK[])")
        if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            raise HTTPException(status_code=404, detail="not_found")
        meta_raw, raw = msg_data[0]
        flags = imaplib.ParseFlags(meta_raw) if meta_raw else ()
        msg = email.message_from_bytes(raw, policy=email.policy.default)

        body = ""
        body_type = "text"
        html_part = msg.get_body(preferencelist=("html",))
        if html_part is not None:
            body = html_part.get_content()
            body_type = "html"
        else:
            plain_part = msg.get_body(preferencelist=("plain",))
            if plain_part is not None:
                body = plain_part.get_content()

        return {
            "id": message_id,
            "subject": _header_value(msg.get("subject")) or "(ohne Betreff)",
            "from": _parse_person(_header_value(msg.get("from"))),
            "to": _parse_people(msg.get_all("to")),
            "cc": _parse_people(msg.get_all("cc")),
            "received_at": _parse_date(_header_value(msg.get("date"))),
            "preview": "",
            "is_read": b"\\Seen" in flags,
            "has_attachments": False,
            "body": body,
            "body_type": body_type,
        }
    finally:
        _disconnect(conn)
