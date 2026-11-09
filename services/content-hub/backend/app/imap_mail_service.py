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
import re
from datetime import timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .imap_config_service import ImapCredentials, get_imap_credentials

logger = logging.getLogger(__name__)

# How much of the raw message to pull for the list view's preview snippet -
# enough for headers (which come first) plus a bit of body, without
# downloading the whole message for every row. BODYSTRUCTURE (see
# _has_attachments) is intentionally NOT truncation-limited - it's returned
# inline by the server regardless of this byte range, so attachment
# detection stays reliable even though the preview text itself may cut off
# mid-body for long messages.
PREVIEW_FETCH_BYTES = 4000
_TAG_PATTERN = re.compile(r"<[^>]+>")


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


def _extract_preview(msg: Any, max_chars: int = 160) -> str:
    """Best-effort plain-text snippet for the list view. msg may be parsed
    from a truncated byte range (see PREVIEW_FETCH_BYTES above), so a
    multipart boundary can be cut off mid-way - the email package's default
    policy tolerates that (collects it as a "defect" rather than raising),
    but this is still wrapped defensively since that's never been verified
    against a real truncated multipart message."""
    try:
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None:
            return ""
        content = part.get_content()
    except Exception:  # noqa: BLE001 - preview is a nice-to-have, never worth failing the request over
        return ""
    text = _TAG_PATTERN.sub(" ", content)
    text = " ".join(text.split())
    return text[:max_chars]


def _has_attachments(meta_raw: bytes | None) -> bool:
    """BODYSTRUCTURE is returned inline in the FETCH response line (not as a
    literal), so this is just a substring check on the same bytes
    imaplib.ParseFlags already scans for flags - no extra parsing needed.
    Heuristic: virtually all IMAP servers include the literal word
    "ATTACHMENT" as the Content-Disposition for attached parts."""
    return bool(meta_raw) and b"ATTACHMENT" in meta_raw.upper()


def test_connection(*, host: str, port: int, use_ssl: bool, username: str, password: str, folder: str) -> None:
    """Try an actual IMAP login + folder select without touching any stored
    account - used to fail fast with a clear error when saving new
    credentials, instead of only discovering a typo'd host/password the
    first time someone opens the mailbox."""
    creds = ImapCredentials(
        id="",
        label="",
        host=host,
        port=port,
        use_ssl=use_ssl,
        username=username,
        password=password,
        folder=folder or "INBOX",
    )
    conn = _connect(creds)
    try:
        _select_folder(conn, creds.folder)
    finally:
        _disconnect(conn)


def _search_criteria(search: str) -> tuple[str, ...]:
    query = (search or "").strip().replace('"', "").replace("\\", "")
    if not query:
        return ("ALL",)
    return ("OR", "SUBJECT", f'"{query}"', "FROM", f'"{query}"')


def list_messages(db: Session, *, account_id: str, limit: int = 30, search: str = "") -> list[dict[str, Any]]:
    creds = get_imap_credentials(db, account_id)
    conn = _connect(creds)
    try:
        _select_folder(conn, creds.folder)
        status, data = conn.uid("search", None, *_search_criteria(search))
        if status != "OK":
            raise HTTPException(status_code=502, detail="imap_search_failed")
        uids = data[0].split() if data and data[0] else []
        uids = uids[-max(1, min(limit, 100)) :]
        uids.reverse()  # most recent first

        messages: list[dict[str, Any]] = []
        for uid in uids:
            status, msg_data = conn.uid(
                "fetch", uid, f"(FLAGS BODYSTRUCTURE BODY.PEEK[]<0.{PREVIEW_FETCH_BYTES}>)"
            )
            if status != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            meta_raw, raw_prefix = msg_data[0]
            flags = imaplib.ParseFlags(meta_raw) if meta_raw else ()
            msg = email.message_from_bytes(raw_prefix, policy=email.policy.default)
            uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
            messages.append(
                {
                    "id": uid_str,
                    "subject": _header_value(msg.get("subject")) or "(ohne Betreff)",
                    "from": _parse_person(_header_value(msg.get("from"))),
                    "received_at": _parse_date(_header_value(msg.get("date"))),
                    "preview": _extract_preview(msg),
                    "is_read": b"\\Seen" in flags,
                    "has_attachments": _has_attachments(meta_raw),
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
        status, msg_data = conn.uid("fetch", uid, "(FLAGS BODYSTRUCTURE BODY.PEEK[])")
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
            "preview": _extract_preview(msg),
            "is_read": b"\\Seen" in flags,
            "has_attachments": _has_attachments(meta_raw),
            "body": body,
            "body_type": body_type,
        }
    finally:
        _disconnect(conn)
