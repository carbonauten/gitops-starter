from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Article, Certificate, Publication, PublicationDelivery, PublishSettings
from .graph_client import get_app_access_token

logger = logging.getLogger(__name__)

CHANNELS = ("teams", "outlook", "notion")
MAX_ATTEMPTS = 3


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def ensure_publish_settings(db: Session) -> PublishSettings:
    settings = get_publish_settings(db)
    if settings:
        return settings

    app_settings = get_settings()
    row = PublishSettings(
        id="default",
        teams_enabled=bool(app_settings.teams_team_id and app_settings.teams_channel_id),
        teams_team_id=app_settings.teams_team_id,
        teams_channel_id=app_settings.teams_channel_id,
        outlook_enabled=bool(app_settings.outlook_sender_id),
        outlook_sender_id=app_settings.outlook_sender_id,
        notion_enabled=bool(app_settings.notion_api_key and app_settings.notion_database_id),
        notion_database_id=app_settings.notion_database_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_publish_settings(db: Session) -> PublishSettings | None:
    return db.get(PublishSettings, "default")


def settings_to_dict(row: PublishSettings, app_settings: Settings | None = None) -> dict:
    app_settings = app_settings or get_settings()
    return {
        "teams_enabled": row.teams_enabled,
        "teams_team_id": row.teams_team_id,
        "teams_channel_id": row.teams_channel_id,
        "outlook_enabled": row.outlook_enabled,
        "outlook_sender_id": row.outlook_sender_id,
        "notion_enabled": row.notion_enabled,
        "notion_database_id": row.notion_database_id,
        "notion_configured": app_settings.notion_configured,
        "graph_configured": app_settings.graph_publish_configured,
        "publish_mock_mode": app_settings.publish_mock_mode,
    }


def channel_status(row: PublishSettings, channel: str, app_settings: Settings | None = None) -> dict:
    app_settings = app_settings or get_settings()
    if channel == "teams":
        ready = row.teams_enabled and row.teams_team_id and row.teams_channel_id and app_settings.graph_publish_configured
    elif channel == "outlook":
        ready = row.outlook_enabled and row.outlook_sender_id and app_settings.graph_publish_configured
    elif channel == "notion":
        ready = row.notion_enabled and row.notion_database_id and app_settings.notion_configured
    else:
        ready = False
    return {
        "channel": channel,
        "enabled": getattr(row, f"{channel}_enabled", False),
        "configured": bool(ready),
        "available": bool(ready) or app_settings.publish_mock_mode,
    }


def list_channels(db: Session) -> list[dict]:
    row = ensure_publish_settings(db)
    return [channel_status(row, channel) for channel in CHANNELS]


def update_publish_settings(db: Session, payload: dict) -> dict:
    row = ensure_publish_settings(db)
    for field in (
        "teams_enabled",
        "teams_team_id",
        "teams_channel_id",
        "outlook_enabled",
        "outlook_sender_id",
        "notion_enabled",
        "notion_database_id",
    ):
        if field in payload and payload[field] is not None:
            setattr(row, field, payload[field])
    db.commit()
    db.refresh(row)
    return settings_to_dict(row)


def delivery_to_dict(delivery: PublicationDelivery) -> dict:
    return {
        "id": delivery.id,
        "channel": delivery.channel,
        "status": delivery.status,
        "error_message": delivery.error_message,
        "external_id": delivery.external_id,
        "external_url": delivery.external_url,
        "attempt_count": delivery.attempt_count,
        "updated_at": delivery.updated_at.isoformat(),
    }


def publication_to_dict(publication: Publication, deliveries: list[PublicationDelivery]) -> dict:
    return {
        "id": publication.id,
        "resource_type": publication.resource_type,
        "resource_id": publication.resource_id,
        "title": publication.title,
        "summary": publication.summary,
        "published_by_id": publication.published_by_id,
        "published_by_name": publication.published_by_name,
        "created_at": publication.created_at.isoformat(),
        "deliveries": [delivery_to_dict(delivery) for delivery in deliveries],
    }


def list_publications(db: Session, *, resource_id: str | None = None, limit: int = 50) -> list[dict]:
    stmt = select(Publication).order_by(Publication.created_at.desc()).limit(limit)
    if resource_id:
        stmt = stmt.where(Publication.resource_id == resource_id)
    publications = list(db.scalars(stmt).all())
    if not publications:
        return []

    publication_ids = [publication.id for publication in publications]
    deliveries = list(
        db.scalars(
            select(PublicationDelivery)
            .where(PublicationDelivery.publication_id.in_(publication_ids))
            .order_by(PublicationDelivery.created_at.asc())
        ).all()
    )
    grouped: dict[str, list[PublicationDelivery]] = {}
    for delivery in deliveries:
        grouped.setdefault(delivery.publication_id, []).append(delivery)
    return [publication_to_dict(publication, grouped.get(publication.id, [])) for publication in publications]


async def _send_teams_message(*, title: str, body_html: str, settings_row: PublishSettings) -> dict:
    app_settings = get_settings()
    if app_settings.publish_mock_mode and not (
        settings_row.teams_enabled and app_settings.graph_publish_configured
    ):
        return {"external_id": "mock-teams", "external_url": "mock://teams/message"}

    token = await get_app_access_token()
    url = (
        f"https://graph.microsoft.com/v1.0/teams/{settings_row.teams_team_id}"
        f"/channels/{settings_row.teams_channel_id}/messages"
    )
    payload = {
        "body": {
            "contentType": "html",
            "content": f"<h3>{title}</h3>{body_html}",
        }
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
        if response.status_code not in {200, 201}:
            raise RuntimeError(response.text)
        data = response.json()
        web_url = data.get("webUrl") or ""
        return {"external_id": data.get("id", ""), "external_url": web_url}


async def _send_outlook_draft(
    *,
    subject: str,
    body_html: str,
    settings_row: PublishSettings,
    to_email: str | None = None,
) -> dict:
    app_settings = get_settings()
    if app_settings.publish_mock_mode and not (
        settings_row.outlook_enabled and app_settings.graph_publish_configured
    ):
        return {"external_id": "mock-outlook", "external_url": "mock://outlook/draft"}

    token = await get_app_access_token()
    url = f"https://graph.microsoft.com/v1.0/users/{settings_row.outlook_sender_id}/messages"
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body_html},
    }
    if to_email:
        message["toRecipients"] = [{"emailAddress": {"address": to_email}}]
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=message)
        if response.status_code not in {200, 201}:
            raise RuntimeError(response.text)
        data = response.json()
        return {
            "external_id": data.get("id", ""),
            "external_url": data.get("webLink") or "",
        }


async def _send_notion_page(*, title: str, summary: str, settings_row: PublishSettings) -> dict:
    app_settings = get_settings()
    if app_settings.publish_mock_mode and not (
        settings_row.notion_enabled and app_settings.notion_configured
    ):
        return {"external_id": "mock-notion", "external_url": "mock://notion/page"}

    payload = {
        "parent": {"database_id": settings_row.notion_database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title[:2000]}}]},
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": summary[:1900]}}],
                },
            }
        ],
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {app_settings.notion_api_key.strip()}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError(response.text)
        data = response.json()
        return {
            "external_id": data.get("id", ""),
            "external_url": data.get("url") or "",
        }


async def _dispatch_delivery(
    delivery: PublicationDelivery,
    *,
    title: str,
    body_html: str,
    summary: str,
    settings_row: PublishSettings,
    to_email: str | None = None,
) -> None:
    try:
        if delivery.channel == "teams":
            result = await _send_teams_message(title=title, body_html=body_html, settings_row=settings_row)
        elif delivery.channel == "outlook":
            result = await _send_outlook_draft(
                subject=title,
                body_html=body_html,
                settings_row=settings_row,
                to_email=to_email,
            )
        elif delivery.channel == "notion":
            result = await _send_notion_page(title=title, summary=summary, settings_row=settings_row)
        else:
            raise RuntimeError(f"unsupported_channel:{delivery.channel}")

        delivery.status = "sent"
        delivery.error_message = None
        delivery.external_id = result.get("external_id")
        delivery.external_url = result.get("external_url")
    except Exception as exc:  # noqa: BLE001
        delivery.status = "failed"
        delivery.error_message = str(exc)[:1000]
        logger.exception("Delivery %s failed for channel %s", delivery.id, delivery.channel)


async def _run_deliveries(
    db: Session,
    deliveries: list[PublicationDelivery],
    *,
    title: str,
    body_html: str,
    summary: str,
    settings_row: PublishSettings,
    to_email: str | None = None,
) -> None:
    for delivery in deliveries:
        delivery.attempt_count += 1
        delivery.status = "pending"
        delivery.updated_at = datetime.now(timezone.utc)
        await _dispatch_delivery(
            delivery,
            title=title,
            body_html=body_html,
            summary=summary,
            settings_row=settings_row,
            to_email=to_email,
        )
        delivery.updated_at = datetime.now(timezone.utc)
    db.commit()


async def publish_article(
    db: Session,
    *,
    article_id: str,
    channels: list[str],
    user: dict,
) -> dict:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    if article.status != "published":
        raise HTTPException(status_code=400, detail="article_not_published")
    if not channels:
        raise HTTPException(status_code=422, detail="validation")

    normalized_channels = []
    for channel in channels:
        if channel not in CHANNELS:
            raise HTTPException(status_code=422, detail="validation")
        if channel not in normalized_channels:
            normalized_channels.append(channel)

    settings_row = ensure_publish_settings(db)
    publication = Publication(
        resource_type="article",
        resource_id=article.id,
        title=article.title,
        summary=_strip_html(article.content)[:500],
        published_by_id=user["db_id"],
        published_by_name=user["name"],
    )
    db.add(publication)
    db.flush()

    deliveries = [
        PublicationDelivery(publication_id=publication.id, channel=channel, status="pending")
        for channel in normalized_channels
    ]
    db.add_all(deliveries)
    db.commit()

    await _run_deliveries(
        db,
        deliveries,
        title=article.title,
        body_html=article.content or f"<p>{article.title}</p>",
        summary=publication.summary,
        settings_row=settings_row,
    )

    db.refresh(publication)
    for delivery in deliveries:
        db.refresh(delivery)
    return publication_to_dict(publication, deliveries)


async def retry_delivery(db: Session, delivery_id: str) -> dict:
    delivery = db.get(PublicationDelivery, delivery_id)
    if not delivery:
        raise HTTPException(status_code=404, detail="not_found")
    if delivery.attempt_count >= MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail="retry_limit_reached")
    if delivery.status == "sent":
        raise HTTPException(status_code=400, detail="already_sent")

    publication = db.get(Publication, delivery.publication_id)
    if not publication:
        raise HTTPException(status_code=404, detail="not_found")

    settings_row = ensure_publish_settings(db)
    body_html = f"<p>{publication.summary}</p>"
    if publication.resource_type == "article":
        article = db.get(Article, publication.resource_id)
        if article and article.content:
            body_html = article.content

    to_email = None
    if publication.resource_type == "certificate_reminder":
        certificate = db.get(Certificate, publication.resource_id)
        if certificate:
            to_email = certificate.responsible_email or None

    delivery.attempt_count += 1
    delivery.status = "pending"
    delivery.updated_at = datetime.now(timezone.utc)
    await _dispatch_delivery(
        delivery,
        title=publication.title,
        body_html=body_html,
        summary=publication.summary,
        settings_row=settings_row,
        to_email=to_email,
    )
    delivery.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(delivery)
    return delivery_to_dict(delivery)


def _expiry_window_days(certificate: Certificate, today: date) -> int | None:
    days = (certificate.valid_to - today).days
    if days in {30, 60, 90}:
        return days
    return None


async def run_certificate_reminders(db: Session, *, user: dict) -> dict:
    settings_row = ensure_publish_settings(db)
    today = datetime.now(timezone.utc).date()
    certificates = list(db.scalars(select(Certificate)).all())
    triggered = []

    for certificate in certificates:
        window = _expiry_window_days(certificate, today)
        if window is None:
            continue

        title = f"Zertifikat läuft in {window} Tagen ab: {certificate.name}"
        summary = (
            f"Zertifikat: {certificate.name}\n"
            f"Kategorie: {certificate.category}\n"
            f"Gültig bis: {certificate.valid_to.isoformat()}\n"
            f"Verantwortlich: {certificate.responsible_name} ({certificate.responsible_email})"
        )
        body_html = f"<p>{summary.replace(chr(10), '<br/>')}</p>"

        publication = Publication(
            resource_type="certificate_reminder",
            resource_id=certificate.id,
            title=title,
            summary=summary,
            published_by_id=user["db_id"],
            published_by_name=user["name"],
        )
        db.add(publication)
        db.flush()

        channels: list[str] = []
        if settings_row.teams_enabled:
            channels.append("teams")
        if settings_row.outlook_enabled:
            channels.append("outlook")
        if not channels and get_settings().publish_mock_mode:
            channels = ["teams", "outlook"]

        deliveries = [
            PublicationDelivery(publication_id=publication.id, channel=channel, status="pending")
            for channel in channels
        ]
        db.add_all(deliveries)
        db.commit()

        await _run_deliveries(
            db,
            deliveries,
            title=title,
            body_html=body_html,
            summary=summary,
            settings_row=settings_row,
            to_email=certificate.responsible_email or None,
        )
        triggered.append(
            {
                "certificate_id": certificate.id,
                "certificate_name": certificate.name,
                "days_until_expiry": window,
                "publication_id": publication.id,
            }
        )

    return {"reminders_sent": len(triggered), "items": triggered}
