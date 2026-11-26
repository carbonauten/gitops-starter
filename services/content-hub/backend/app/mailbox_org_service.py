from __future__ import annotations

import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import caldav_client
from .imap_config_service import ImapCredentials
from .imap_mail_service import get_attachment, get_message, list_folders, list_messages, test_connection
from .user_integration_store import (
    delete_user_integration,
    get_user_integration,
    read_user_access_token,
    save_user_integration,
    user_integration_status,
)

logger = logging.getLogger(__name__)

# mailbox.org (Berlin-hosted, GDPR/German data protection) has no OAuth - like
# Strato, it only publishes IMAP/SMTP/CalDAV. "Connecting" an account here
# means entering the mailbox.org login (ideally an app-specific password)
# directly, verified with a real IMAP login before it's saved - same
# approach as the existing admin-configured IMAP accounts, just per-user.
PROVIDER = "mailbox_org"
IMAP_HOST = "imap.mailbox.org"
IMAP_PORT = 993
SMTP_HOST = "smtp.mailbox.org"
SMTP_PORT = 587
CALDAV_BASE = "https://dav.mailbox.org/"
DEFAULT_FOLDER = "INBOX"


def _credentials(db: Session, *, user_id: str) -> ImapCredentials:
    row = get_user_integration(db, user_id=user_id, provider=PROVIDER)
    if not row:
        raise HTTPException(status_code=400, detail="mailbox_org_not_connected")
    password = read_user_access_token(row)
    if not password:
        raise HTTPException(status_code=400, detail="mailbox_org_not_connected")
    return ImapCredentials(
        id=f"mailbox_org:{user_id}",
        label="mailbox.org",
        host=IMAP_HOST,
        port=IMAP_PORT,
        use_ssl=True,
        username=row.account_label,
        password=password,
        folder=DEFAULT_FOLDER,
    )


def mailbox_org_status(db: Session, *, user_id: str) -> dict[str, Any]:
    return user_integration_status(db, user_id=user_id, provider=PROVIDER)


def connect_mailbox_org(db: Session, *, user_id: str, email: str, password: str) -> dict[str, Any]:
    email = (email or "").strip()
    password = password or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="validation")

    try:
        test_connection(
            host=IMAP_HOST, port=IMAP_PORT, use_ssl=True, username=email, password=password, folder=DEFAULT_FOLDER
        )
    except HTTPException:
        raise HTTPException(status_code=400, detail="mailbox_org_login_failed") from None

    save_user_integration(
        db,
        user_id=user_id,
        provider=PROVIDER,
        access_token=password,
        account_label=email,
        calendar_enabled=True,
        mail_enabled=True,
    )
    return mailbox_org_status(db, user_id=user_id)


def disconnect_mailbox_org(db: Session, *, user_id: str) -> None:
    delete_user_integration(db, user_id=user_id, provider=PROVIDER)


def mailbox_org_folders(db: Session, *, user_id: str) -> list[dict[str, Any]]:
    return list_folders(creds=_credentials(db, user_id=user_id))


def mailbox_org_messages(
    db: Session, *, user_id: str, limit: int = 30, search: str = "", folder: str | None = None
) -> list[dict[str, Any]]:
    return list_messages(creds=_credentials(db, user_id=user_id), limit=limit, search=search, folder=folder)


def mailbox_org_message(db: Session, *, user_id: str, message_id: str, folder: str | None = None) -> dict[str, Any]:
    return get_message(creds=_credentials(db, user_id=user_id), message_id=message_id, folder=folder)


def mailbox_org_attachment(
    db: Session, *, user_id: str, message_id: str, attachment_index: int, folder: str | None = None
) -> tuple[bytes, str, str]:
    return get_attachment(
        creds=_credentials(db, user_id=user_id),
        message_id=message_id,
        attachment_index=attachment_index,
        folder=folder,
    )


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_invite_ics(
    *,
    uid: str,
    method: str,
    title: str,
    start: datetime,
    end: datetime,
    location: str,
    description: str,
    organizer_email: str,
    organizer_name: str,
    attendee_emails: list[str],
) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//elphen//Meetings//DE",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_ics_datetime(datetime.now(timezone.utc))}",
        f"DTSTART:{_ics_datetime(start)}",
        f"DTEND:{_ics_datetime(end)}",
        f"SUMMARY:{_ics_escape(title)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"LOCATION:{_ics_escape(location)}",
        f"ORGANIZER;CN={_ics_escape(organizer_name)}:mailto:{organizer_email}",
    ]
    for attendee in attendee_emails:
        lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE;CN={_ics_escape(attendee)}:mailto:{attendee}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def _send_invite_email(
    *,
    username: str,
    password: str,
    organizer_name: str,
    attendee_emails: list[str],
    subject: str,
    body_text: str,
    ics: bytes,
) -> bool:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{organizer_name} <{username}>"
    message["To"] = ", ".join(attendee_emails)
    message.set_content(body_text)
    message.add_attachment(
        ics,
        maintype="text",
        subtype="calendar",
        filename="invite.ics",
        params={"method": "REQUEST"},
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as client:
            client.starttls()
            client.login(username, password)
            client.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("mailbox.org invite email failed: %s", exc)
        return False
    return True


def send_meeting_invite(
    db: Session,
    *,
    user_id: str,
    organizer_name: str,
    title: str,
    start: datetime,
    end: datetime,
    meeting_url: str,
    attendee_emails: list[str],
) -> bool:
    """Puts the event on the organizer's own mailbox.org calendar (CalDAV)
    and, if that account is connected and there are attendees, emails them a
    standards-based calendar invite (.ics with METHOD:REQUEST) via the same
    account's SMTP - CalDAV alone doesn't guarantee the server emails
    attendees for you, so this is the reliable path. Returns whether the
    attendee invite email went out; the CalDAV write is best-effort and
    doesn't affect the return value."""
    row = get_user_integration(db, user_id=user_id, provider=PROVIDER)
    if not row or not row.calendar_enabled:
        return False
    password = read_user_access_token(row)
    if not password:
        return False
    username = row.account_label

    uid = f"{uuid.uuid4()}@elphen"
    description = f"Meeting beitreten: {meeting_url}"

    calendar_url = caldav_client.discover_calendar_url(CALDAV_BASE, username=username, password=password)
    if calendar_url:
        own_copy = _build_invite_ics(
            uid=uid,
            method="PUBLISH",
            title=title,
            start=start,
            end=end,
            location=meeting_url,
            description=description,
            organizer_email=username,
            organizer_name=organizer_name,
            attendee_emails=attendee_emails,
        )
        if not caldav_client.create_event(calendar_url, username=username, password=password, ics=own_copy, uid=uid):
            logger.warning("mailbox.org CalDAV event creation failed for %s", username)
    else:
        logger.warning("mailbox.org CalDAV calendar discovery failed for %s", username)

    if not attendee_emails:
        return False

    invite_ics = _build_invite_ics(
        uid=uid,
        method="REQUEST",
        title=title,
        start=start,
        end=end,
        location=meeting_url,
        description=description,
        organizer_email=username,
        organizer_name=organizer_name,
        attendee_emails=attendee_emails,
    )
    return _send_invite_email(
        username=username,
        password=password,
        organizer_name=organizer_name,
        attendee_emails=attendee_emails,
        subject=f"Einladung: {title}",
        body_text=description,
        ics=invite_ics,
    )
