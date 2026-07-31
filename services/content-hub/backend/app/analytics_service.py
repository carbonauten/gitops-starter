from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .certificates import compute_certificate_status, expiry_window_end
from .database import Article, AuditLog, Certificate, FileAsset, Publication, PublicationDelivery


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _range_start(days: int) -> datetime:
    return _utc_now() - timedelta(days=days)


def _count_by(db: Session, model: type, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).group_by(column)).all()
    return {str(key): int(count) for key, count in rows if key is not None}


def _count_expiring(db: Session, days: int, today: date) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.valid_to >= today,
                Certificate.valid_to <= expiry_window_end(days, today),
            )
        )
        or 0
    )


def _fill_daily_counts(raw: dict[str, int], days: int, today: date) -> list[dict[str, Any]]:
    start = today - timedelta(days=days - 1)
    series: list[dict[str, Any]] = []
    cursor = start
    while cursor <= today:
        key = cursor.isoformat()
        series.append({"date": key, "count": raw.get(key, 0)})
        cursor += timedelta(days=1)
    return series


def build_analytics_overview(db: Session, *, days: int = 90) -> dict[str, Any]:
    days = max(7, min(days, 365))
    today = date.today()
    since = _range_start(days)

    article_total = db.scalar(select(func.count()).select_from(Article)) or 0
    articles_by_status = _count_by(db, Article, Article.status)

    certificates = list(db.scalars(select(Certificate)).all())
    cert_by_status: dict[str, int] = defaultdict(int)
    cert_by_category: dict[str, int] = defaultdict(int)
    for cert in certificates:
        status = compute_certificate_status(cert.valid_to, cert.renewal_in_progress, today)
        cert_by_status[status] += 1
        cert_by_category[cert.category or "other"] += 1

    renewals_pending = (
        db.scalar(
            select(func.count()).select_from(Certificate).where(Certificate.renewal_approval_status == "pending")
        )
        or 0
    )

    publication_total = db.scalar(select(func.count()).select_from(Publication)) or 0
    publications_in_range = list(
        db.scalars(select(Publication).where(Publication.created_at >= since).order_by(Publication.created_at.desc())).all()
    )
    daily_raw: dict[str, int] = defaultdict(int)
    for pub in publications_in_range:
        created = pub.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        daily_raw[created.astimezone(timezone.utc).date().isoformat()] += 1

    deliveries = list(
        db.scalars(
            select(PublicationDelivery).where(PublicationDelivery.created_at >= since)
        ).all()
    )
    by_status: dict[str, int] = defaultdict(int)
    channel_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"sent": 0, "failed": 0, "pending": 0, "total": 0})
    for delivery in deliveries:
        status = delivery.status or "pending"
        by_status[status] += 1
        bucket = channel_stats[delivery.channel]
        bucket["total"] += 1
        if status in ("sent", "success"):
            bucket["sent"] += 1
        elif status in ("failed", "error"):
            bucket["failed"] += 1
        else:
            bucket["pending"] += 1

    by_channel = [
        {
            "channel": channel,
            "sent": stats["sent"],
            "failed": stats["failed"],
            "pending": stats["pending"],
            "total": stats["total"],
        }
        for channel, stats in sorted(channel_stats.items())
    ]

    recent_slice = publications_in_range[:10]
    recent_ids = [pub.id for pub in recent_slice]
    recent_delivery_map: dict[str, list[PublicationDelivery]] = defaultdict(list)
    if recent_ids:
        for delivery in db.scalars(
            select(PublicationDelivery).where(PublicationDelivery.publication_id.in_(recent_ids))
        ).all():
            recent_delivery_map[delivery.publication_id].append(delivery)

    recent_pubs: list[dict[str, Any]] = []
    for pub in recent_slice:
        pub_deliveries = recent_delivery_map.get(pub.id, [])
        recent_pubs.append(
            {
                "id": pub.id,
                "title": pub.title,
                "published_by_name": pub.published_by_name,
                "created_at": pub.created_at.isoformat() if pub.created_at else None,
                "channels_ok": sum(1 for d in pub_deliveries if d.status in ("sent", "success")),
                "channels_failed": sum(1 for d in pub_deliveries if d.status in ("failed", "error")),
                "channels_total": len(pub_deliveries),
            }
        )

    author_rows = db.execute(
        select(Article.author_name, func.count())
        .group_by(Article.author_name)
        .order_by(func.count().desc())
        .limit(8)
    ).all()
    top_authors = [{"author_name": name or "—", "article_count": int(count)} for name, count in author_rows]

    audit_in_range = (
        db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.created_at >= since)) or 0
    )
    file_total = db.scalar(select(func.count()).select_from(FileAsset)) or 0

    return {
        "generated_at": _utc_now().isoformat(),
        "range_days": days,
        "articles": {
            "total": int(article_total),
            "by_status": articles_by_status,
        },
        "certificates": {
            "total": len(certificates),
            "by_status": dict(cert_by_status),
            "by_category": dict(cert_by_category),
            "expiring_30": _count_expiring(db, 30, today),
            "expiring_60": _count_expiring(db, 60, today),
            "expiring_90": _count_expiring(db, 90, today),
            "renewals_pending": int(renewals_pending),
        },
        "publications": {
            "total": int(publication_total),
            "in_range": len(publications_in_range),
            "by_day": _fill_daily_counts(daily_raw, days, today),
            "deliveries": {
                "total": len(deliveries),
                "by_status": dict(by_status),
                "by_channel": by_channel,
            },
            "recent": recent_pubs,
        },
        "files": {"total": int(file_total)},
        "activity": {
            "top_authors": top_authors,
            "audit_actions_in_range": int(audit_in_range),
        },
    }
