from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit_service import log_audit
from .config import Settings, get_settings
from .database import Article, FileAsset, FileFolder
from .entra_config_service import resolve_entra_credentials
from .file_folder_service import resolve_upload_folder
from .storage import save_upload
from .user_integration_store import (
    delete_user_integration,
    get_user_integration,
    read_user_access_token,
    read_user_refresh_token,
    save_user_integration,
    user_integration_status,
)
from .version_service import article_snapshot, record_revision

logger = logging.getLogger(__name__)

# Personal Microsoft 365 for the signed-in user (calendar, mailbox, OneDrive).
# ReadWrite stays; users avoid "Need admin approval" after one org-wide admin consent.
OUTLOOK_USER_SCOPES = (
    "offline_access User.Read Calendars.ReadWrite Mail.ReadWrite Files.Read"
)


def outlook_redirect_uri(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    origin = settings.effective_public_origin or "http://localhost:8080"
    return f"{origin.rstrip('/')}/api/integrations/outlook/callback"


def outlook_authorize_url(state: str, db: Session | None = None, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    creds = resolve_entra_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="microsoft_auth_unavailable")
    params = {
        "client_id": creds.client_id,
        "response_type": "code",
        "redirect_uri": outlook_redirect_uri(settings),
        "response_mode": "query",
        "scope": OUTLOOK_USER_SCOPES,
        "state": state,
        # Do not force prompt=consent — that often surfaces "Need admin approval".
        # select_account lets each user pick their mailbox without re-consent drama.
        "prompt": "select_account",
    }
    return (
        f"https://login.microsoftonline.com/{creds.tenant_id}/oauth2/v2.0/authorize?"
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


async def _exchange_outlook_code(code: str, settings: Settings, db: Session) -> dict[str, Any]:
    creds = resolve_entra_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="microsoft_auth_unavailable")
    token_url = f"https://login.microsoftonline.com/{creds.tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
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

    payload = await _exchange_outlook_code(code, settings, db)
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
    creds = resolve_entra_credentials(db)
    if not creds.configured:
        raise HTTPException(status_code=400, detail="microsoft_auth_unavailable")
    token_url = f"https://login.microsoftonline.com/{creds.tenant_id}/oauth2/v2.0/token"
    data = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
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
    from .entra_config_service import entra_status as platform_entra_status

    creds = resolve_entra_credentials(db)
    platform = platform_entra_status(db) if creds.configured else {}
    return {
        **user_integration_status(db, user_id=user_id, provider="outlook"),
        "oauth_available": creds.configured,
        "oauth_source": creds.source if creds.configured else "none",
        "admin_consent_url": platform.get("admin_consent_url") or "",
        "delegated_scopes": platform.get("delegated_scopes") or [
            "User.Read",
            "Mail.ReadWrite",
            "Calendars.ReadWrite",
            "Files.Read",
            "offline_access",
        ],
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


def _require_outlook_mail(db: Session, *, user_id: str):
    row = get_user_integration(db, user_id=user_id, provider="outlook")
    if not row or not row.mail_enabled:
        raise HTTPException(status_code=400, detail="outlook_mail_not_connected")
    return row


def _graph_recipient(entry: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(entry, dict):
        return {"name": "", "email": ""}
    addr = entry.get("emailAddress") or {}
    if not isinstance(addr, dict):
        return {"name": "", "email": ""}
    return {
        "name": str(addr.get("name") or "").strip(),
        "email": str(addr.get("address") or "").strip(),
    }


def _format_recipients(entries: list[Any] | None) -> str:
    parts: list[str] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        person = _graph_recipient(entry)
        if person["name"] and person["email"]:
            parts.append(f'{person["name"]} <{person["email"]}>')
        elif person["email"]:
            parts.append(person["email"])
        elif person["name"]:
            parts.append(person["name"])
    return ", ".join(parts)


def _message_summary(item: dict[str, Any]) -> dict[str, Any]:
    sender = _graph_recipient(item.get("from"))
    return {
        "id": str(item.get("id") or ""),
        "subject": str(item.get("subject") or "").strip() or "(ohne Betreff)",
        "from": sender,
        "received_at": item.get("receivedDateTime") or None,
        "preview": str(item.get("bodyPreview") or "").strip(),
        "is_read": bool(item.get("isRead")),
        "has_attachments": bool(item.get("hasAttachments")),
        "web_link": str(item.get("webLink") or ""),
    }


def _message_detail(item: dict[str, Any]) -> dict[str, Any]:
    summary = _message_summary(item)
    body = item.get("body") or {}
    body_content = ""
    body_type = "text"
    if isinstance(body, dict):
        body_content = str(body.get("content") or "")
        body_type = str(body.get("contentType") or "text").lower()
    summary.update(
        {
            "to": [_graph_recipient(entry) for entry in (item.get("toRecipients") or []) if isinstance(entry, dict)],
            "cc": [_graph_recipient(entry) for entry in (item.get("ccRecipients") or []) if isinstance(entry, dict)],
            "body": body_content,
            "body_type": body_type if body_type in {"html", "text"} else "text",
        }
    )
    return summary


def _safe_filename(subject: str) -> str:
    cleaned = re.sub(r"[^\w\s\-äöüÄÖÜß.]+", "", subject, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)[:80] or "outlook-email"
    return f"{cleaned}.html"


def _email_html_document(detail: dict[str, Any]) -> str:
    subject = html.escape(str(detail.get("subject") or ""))
    sender = detail.get("from") or {}
    from_line = html.escape(
        f'{sender.get("name") or ""} <{sender.get("email") or ""}>'.strip()
        if sender.get("email") or sender.get("name")
        else ""
    )
    to_line = html.escape(
        ", ".join(
            f'{p.get("name") or ""} <{p.get("email") or ""}>'.strip()
            for p in (detail.get("to") or [])
            if p.get("email") or p.get("name")
        )
    )
    received = html.escape(str(detail.get("received_at") or ""))
    body = detail.get("body") or ""
    if (detail.get("body_type") or "text") == "html":
        body_html = body
    else:
        body_html = f"<pre style=\"white-space:pre-wrap;font-family:inherit\">{html.escape(body)}</pre>"
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>{subject}</title></head><body>"
        f"<h1>{subject}</h1>"
        f"<p><strong>Von:</strong> {from_line}</p>"
        f"<p><strong>An:</strong> {to_line}</p>"
        f"<p><strong>Datum:</strong> {received}</p>"
        "<hr/>"
        f"{body_html}"
        "</body></html>"
    )


def _email_article_content(detail: dict[str, Any]) -> str:
    sender = detail.get("from") or {}
    from_line = html.escape(
        f'{sender.get("name") or ""} <{sender.get("email") or ""}>'.strip()
        if sender.get("email") or sender.get("name")
        else "—"
    )
    to_line = html.escape(
        ", ".join(
            f'{p.get("name") or ""} <{p.get("email") or ""}>'.strip()
            for p in (detail.get("to") or [])
            if p.get("email") or p.get("name")
        )
        or "—"
    )
    received = html.escape(str(detail.get("received_at") or "—"))
    subject = html.escape(str(detail.get("subject") or ""))
    body = detail.get("body") or ""
    if (detail.get("body_type") or "text") == "html":
        body_html = body
    else:
        body_html = f"<pre style=\"white-space:pre-wrap;font-family:inherit\">{html.escape(body)}</pre>"
    web_link = str(detail.get("web_link") or "").strip()
    link_html = (
        f'<p><a href="{html.escape(web_link)}" target="_blank" rel="noopener">In Outlook öffnen</a></p>'
        if web_link
        else ""
    )
    return (
        f"<p><strong>Von:</strong> {from_line}</p>"
        f"<p><strong>An:</strong> {to_line}</p>"
        f"<p><strong>Datum:</strong> {received}</p>"
        f"<p><strong>Betreff:</strong> {subject}</p>"
        f"{link_html}"
        "<hr/>"
        f"{body_html}"
    )


def ensure_emails_folder(db: Session) -> FileFolder:
    existing = db.scalar(select(FileFolder).where(FileFolder.slug == "emails", FileFolder.parent_id.is_(None)))
    if existing:
        return existing
    folder = FileFolder(name="E-Mails", slug="emails", parent_id=None, sort_order=50)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


async def fetch_outlook_messages(
    db: Session,
    *,
    user_id: str,
    top: int = 25,
    search: str = "",
) -> list[dict[str, Any]]:
    _require_outlook_mail(db, user_id=user_id)
    token = await get_outlook_access_token(db, user_id=user_id)
    if not token:
        raise HTTPException(status_code=400, detail="outlook_not_connected")

    limit = max(1, min(int(top or 25), 50))
    params: dict[str, str] = {
        "$top": str(limit),
        "$select": "id,subject,from,receivedDateTime,bodyPreview,isRead,hasAttachments,webLink",
        "$orderby": "receivedDateTime desc",
    }
    query = (search or "").strip()
    if query:
        # $search cannot be combined with $orderby on Graph mail; drop orderby.
        params.pop("$orderby", None)
        params["$search"] = f'"{query}"'

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
            headers={
                "Authorization": f"Bearer {token}",
                "ConsistencyLevel": "eventual",
            },
            params=params,
        )
        if response.status_code != 200:
            logger.warning("Outlook mail list failed: %s", response.text)
            raise HTTPException(status_code=502, detail="outlook_mail_failed")
        payload = response.json()

    return [_message_summary(item) for item in payload.get("value", []) if isinstance(item, dict)]


async def get_outlook_message(db: Session, *, user_id: str, message_id: str) -> dict[str, Any]:
    _require_outlook_mail(db, user_id=user_id)
    token = await get_outlook_access_token(db, user_id=user_id)
    if not token:
        raise HTTPException(status_code=400, detail="outlook_not_connected")

    mid = (message_id or "").strip()
    if not mid:
        raise HTTPException(status_code=400, detail="validation")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{quote(mid, safe='')}",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "$select": (
                    "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                    "body,bodyPreview,webLink,hasAttachments,isRead"
                ),
            },
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="not_found")
        if response.status_code != 200:
            logger.warning("Outlook mail get failed: %s", response.text)
            raise HTTPException(status_code=502, detail="outlook_mail_failed")
        payload = response.json()

    return _message_detail(payload)


async def save_outlook_message(
    db: Session,
    *,
    user_id: str,
    user: dict[str, Any],
    message_id: str,
    destination: str = "both",
) -> dict[str, Any]:
    """Persist a mailbox message as draft article and/or HTML file for any connected user."""
    dest = (destination or "both").strip().lower()
    if dest not in {"article", "file", "both"}:
        raise HTTPException(status_code=400, detail="validation")

    detail = await get_outlook_message(db, user_id=user_id, message_id=message_id)
    actor_id = str(user.get("id") or user.get("db_id") or user_id)
    actor_name = str(user.get("name") or "User")
    actor_email = str(user.get("email") or "")

    result: dict[str, Any] = {"message": detail, "article": None, "file": None}

    if dest in {"article", "both"}:
        article = Article(
            title=str(detail.get("subject") or "(ohne Betreff)")[:500],
            content=_email_article_content(detail),
            status="draft",
            template=None,
            review_comment="Gespeichert aus Outlook",
            author_id=actor_id,
            author_name=actor_name,
            author_email=actor_email,
        )
        db.add(article)
        db.commit()
        db.refresh(article)
        record_revision(
            db,
            entity_type="article",
            entity_id=article.id,
            snapshot=article_snapshot(article),
            actor=user,
        )
        db.commit()
        log_audit(
            db,
            entity_type="article",
            entity_id=article.id,
            action="create_from_outlook",
            actor=user,
            details={"outlook_message_id": detail.get("id"), "subject": article.title},
        )
        result["article"] = {
            "id": article.id,
            "title": article.title,
            "status": article.status,
        }

    if dest in {"file", "both"}:
        folder = ensure_emails_folder(db)
        target = resolve_upload_folder(db, folder_id=folder.id, folder_slug=None)
        content = _email_html_document(detail).encode("utf-8")
        original_name = _safe_filename(str(detail.get("subject") or "outlook-email"))
        stored_name, storage_path, _ = save_upload(content, original_name)
        file_asset = FileAsset(
            original_name=original_name,
            stored_name=stored_name,
            content_type="text/html; charset=utf-8",
            size_bytes=len(content),
            folder=target.slug,
            folder_id=target.id,
            storage_path=storage_path,
            uploaded_by_id=actor_id,
            uploaded_by_name=actor_name,
        )
        db.add(file_asset)
        db.commit()
        db.refresh(file_asset)
        log_audit(
            db,
            entity_type="file",
            entity_id=file_asset.id,
            action="create_from_outlook",
            actor=user,
            details={"outlook_message_id": detail.get("id"), "name": original_name},
        )
        result["file"] = {
            "id": file_asset.id,
            "original_name": file_asset.original_name,
            "folder": file_asset.folder,
        }

    return result
