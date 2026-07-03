from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Article, Certificate, SyncLog

logger = logging.getLogger(__name__)

SYNCABLE_ARTICLE_FIELDS = (
    "id",
    "title",
    "content",
    "status",
    "template",
    "author_id",
    "author_name",
    "author_email",
    "created_at",
    "updated_at",
)

SYNCABLE_CERTIFICATE_FIELDS = (
    "id",
    "name",
    "category",
    "issuer",
    "valid_from",
    "valid_to",
    "renewal_in_progress",
    "responsible_name",
    "responsible_email",
    "file_asset_id",
    "notes",
    "created_by_id",
    "created_by_name",
    "created_at",
    "updated_at",
)


def _serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _article_payload(article: Article) -> dict:
    return {field: _serialize_value(getattr(article, field)) for field in SYNCABLE_ARTICLE_FIELDS}


def _certificate_payload(certificate: Certificate) -> dict:
    return {field: _serialize_value(getattr(certificate, field)) for field in SYNCABLE_CERTIFICATE_FIELDS}


def export_sync_payload(db: Session) -> dict:
    settings = get_settings()
    articles = list(db.scalars(select(Article)).all())
    certificates = list(db.scalars(select(Certificate)).all())
    return {
        "region": settings.deployment_region,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "articles": [_article_payload(article) for article in articles],
        "certificates": [_certificate_payload(certificate) for certificate in certificates],
    }


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _upsert_article(db: Session, payload: dict, local_region: str, remote_region: str) -> str:
    article = db.get(Article, payload["id"])
    remote_updated = _normalize_utc(_parse_datetime(payload.get("updated_at")))
    if article:
        local_updated = _normalize_utc(article.updated_at)
        if local_updated and remote_updated and local_updated > remote_updated:
            return "skipped"
        for field in SYNCABLE_ARTICLE_FIELDS:
            if field in {"created_at", "updated_at"}:
                continue
            if field in payload:
                setattr(article, field, payload[field])
        article.updated_at = remote_updated or article.updated_at
        return "updated"

    article = Article(
        id=payload["id"],
        title=payload.get("title", ""),
        content=payload.get("content", ""),
        status=payload.get("status", "draft"),
        template=payload.get("template"),
        author_id=payload.get("author_id", remote_region),
        author_name=payload.get("author_name", "Synced"),
        author_email=payload.get("author_email", ""),
    )
    article.created_at = _parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc)
    article.updated_at = remote_updated or article.created_at
    db.add(article)
    return "created"


def _upsert_certificate(db: Session, payload: dict) -> str:
    certificate = db.get(Certificate, payload["id"])
    remote_updated = _normalize_utc(_parse_datetime(payload.get("updated_at")))
    if certificate:
        local_updated = _normalize_utc(certificate.updated_at)
        if local_updated and remote_updated and local_updated > remote_updated:
            return "skipped"
        for field in SYNCABLE_CERTIFICATE_FIELDS:
            if field in {"created_at", "updated_at", "valid_from", "valid_to"}:
                continue
            if field in payload:
                setattr(certificate, field, payload[field])
        certificate.valid_from = _parse_date(payload.get("valid_from")) or certificate.valid_from
        certificate.valid_to = _parse_date(payload.get("valid_to")) or certificate.valid_to
        certificate.updated_at = remote_updated or certificate.updated_at
        return "updated"

    today = date.today()
    certificate = Certificate(
        id=payload["id"],
        name=payload.get("name", ""),
        category=payload.get("category", "compliance"),
        issuer=payload.get("issuer", ""),
        valid_from=_parse_date(payload.get("valid_from")) or today,
        valid_to=_parse_date(payload.get("valid_to")) or today,
        renewal_in_progress=bool(payload.get("renewal_in_progress", False)),
        responsible_name=payload.get("responsible_name", ""),
        responsible_email=payload.get("responsible_email", ""),
        file_asset_id=payload.get("file_asset_id"),
        notes=payload.get("notes", ""),
        created_by_id=payload.get("created_by_id", "sync"),
        created_by_name=payload.get("created_by_name", "Sync"),
    )
    certificate.created_at = _parse_datetime(payload.get("created_at")) or datetime.now(timezone.utc)
    certificate.updated_at = remote_updated or certificate.created_at
    db.add(certificate)
    return "created"


def import_sync_payload(db: Session, payload: dict) -> dict:
    settings = get_settings()
    if payload.get("region") == settings.deployment_region:
        raise HTTPException(status_code=400, detail="sync_same_region")

    article_stats = {"created": 0, "updated": 0, "skipped": 0}
    for article in payload.get("articles", []):
        result = _upsert_article(db, article, settings.deployment_region, payload.get("region", "peer"))
        article_stats[result] = article_stats.get(result, 0) + 1

    certificate_stats = {"created": 0, "updated": 0, "skipped": 0}
    for certificate in payload.get("certificates", []):
        result = _upsert_certificate(db, certificate)
        certificate_stats[result] = certificate_stats.get(result, 0) + 1

    db.commit()
    return {
        "articles": article_stats,
        "certificates": certificate_stats,
        "source_region": payload.get("region"),
        "exported_at": payload.get("exported_at"),
    }


def _log_sync(
    db: Session,
    *,
    direction: str,
    status: str,
    article_count: int,
    certificate_count: int,
    message: str = "",
) -> SyncLog:
    entry = SyncLog(
        direction=direction,
        status=status,
        article_count=article_count,
        certificate_count=certificate_count,
        message=message[:1000],
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def sync_status(db: Session, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    last_success = db.scalar(
        select(SyncLog)
        .where(SyncLog.status == "success")
        .order_by(SyncLog.created_at.desc())
        .limit(1)
    )
    last_failure = db.scalar(
        select(SyncLog)
        .where(SyncLog.status == "failed")
        .order_by(SyncLog.created_at.desc())
        .limit(1)
    )
    article_count = int(db.scalar(select(func.count()).select_from(Article)) or 0)
    certificate_count = int(db.scalar(select(func.count()).select_from(Certificate)) or 0)
    return {
        "region": settings.deployment_region,
        "peer_region": settings.sync_peer_region,
        "peer_url": settings.sync_peer_url or None,
        "sync_enabled": settings.sync_configured,
        "storage_backend": settings.storage_backend,
        "article_count": article_count,
        "certificate_count": certificate_count,
        "last_success_at": last_success.created_at.isoformat() if last_success else None,
        "last_failure_at": last_failure.created_at.isoformat() if last_failure else None,
        "last_failure_message": last_failure.message if last_failure else None,
    }


async def push_to_peer(db: Session, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not settings.sync_configured:
        raise HTTPException(status_code=400, detail="sync_not_configured")

    payload = export_sync_payload(db)
    headers = {"X-Sync-Key": settings.sync_api_key.strip(), "Content-Type": "application/json"}
    url = f"{settings.sync_peer_url.rstrip('/')}/api/sync/import"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise RuntimeError(response.text)
            result = response.json()
    except Exception as exc:  # noqa: BLE001
        _log_sync(
            db,
            direction="push",
            status="failed",
            article_count=len(payload["articles"]),
            certificate_count=len(payload["certificates"]),
            message=str(exc),
        )
        raise HTTPException(status_code=502, detail="sync_push_failed") from exc

    _log_sync(
        db,
        direction="push",
        status="success",
        article_count=len(payload["articles"]),
        certificate_count=len(payload["certificates"]),
        message=f"peer={result.get('source_region')}",
    )
    return {
        "direction": "push",
        "article_count": len(payload["articles"]),
        "certificate_count": len(payload["certificates"]),
        "result": result,
    }


async def pull_from_peer(db: Session, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not settings.sync_configured:
        raise HTTPException(status_code=400, detail="sync_not_configured")

    headers = {"X-Sync-Key": settings.sync_api_key.strip()}
    url = f"{settings.sync_peer_url.rstrip('/')}/api/sync/export"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(response.text)
            payload = response.json()
        result = import_sync_payload(db, payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        _log_sync(db, direction="pull", status="failed", article_count=0, certificate_count=0, message=str(exc))
        raise HTTPException(status_code=502, detail="sync_pull_failed") from exc

    _log_sync(
        db,
        direction="pull",
        status="success",
        article_count=result["articles"].get("created", 0) + result["articles"].get("updated", 0),
        certificate_count=result["certificates"].get("created", 0) + result["certificates"].get("updated", 0),
        message=f"source={result.get('source_region')}",
    )
    return {"direction": "pull", "result": result}


async def run_full_sync(db: Session) -> dict:
    push_result = await push_to_peer(db)
    pull_result = await pull_from_peer(db)
    return {"push": push_result, "pull": pull_result}
