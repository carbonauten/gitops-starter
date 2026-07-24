from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .certificates import compute_certificate_status, days_until_expiry, expiry_window_end
from .database import Article, Certificate, Publication
from .roles import APPROVAL_ROLES, CERT_APPROVAL_ROLES


def _article_summary(article: Article) -> dict[str, Any]:
    return {
        "id": article.id,
        "title": article.title or "Untitled",
        "status": article.status,
        "scheduled_publish_at": article.scheduled_publish_at.isoformat() if article.scheduled_publish_at else None,
        "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        "author_name": article.author_name,
    }


def _certificate_summary(certificate: Certificate, today: date) -> dict[str, Any]:
    return {
        "id": certificate.id,
        "name": certificate.name,
        "status": compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress, today),
        "valid_to": certificate.valid_to.isoformat(),
        "days_until_expiry": days_until_expiry(certificate.valid_to, today),
        "responsible_name": certificate.responsible_name,
        "responsible_email": certificate.responsible_email,
    }


def build_home_dashboard(db: Session, user: dict) -> dict[str, Any]:
    today = date.today()
    user_id = user.get("id") or ""
    email = (user.get("email") or "").strip().lower()
    role = user.get("role") or ""

    my_drafts = list(
        db.scalars(
            select(Article)
            .where(Article.author_id == user_id, Article.status.in_(("draft", "rejected")))
            .order_by(Article.updated_at.desc())
            .limit(8)
        ).all()
    )
    my_in_review = list(
        db.scalars(
            select(Article)
            .where(Article.author_id == user_id, Article.status == "review")
            .order_by(Article.updated_at.desc())
            .limit(8)
        ).all()
    )

    approvals: list[dict[str, Any]] = []
    if role in APPROVAL_ROLES:
        pending_articles = list(
            db.scalars(
                select(Article).where(Article.status == "review").order_by(Article.updated_at.desc()).limit(8)
            ).all()
        )
        for article in pending_articles:
            approvals.append({"kind": "article_review", **_article_summary(article)})
    if role in CERT_APPROVAL_ROLES or role in APPROVAL_ROLES:
        pending_renewals = list(
            db.scalars(
                select(Certificate)
                .where(Certificate.renewal_approval_status == "pending")
                .order_by(Certificate.updated_at.desc())
                .limit(8)
            ).all()
        )
        for certificate in pending_renewals:
            approvals.append({"kind": "certificate_renewal", **_certificate_summary(certificate, today)})

    cert_query = select(Certificate).order_by(Certificate.valid_to.asc()).limit(12)
    if email:
        cert_query = (
            select(Certificate)
            .where(
                or_(
                    Certificate.responsible_email.ilike(email),
                    Certificate.created_by_id == user_id,
                )
            )
            .order_by(Certificate.valid_to.asc())
            .limit(12)
        )
    my_certificates = list(db.scalars(cert_query).all())
    my_expiring = [
        _certificate_summary(certificate, today)
        for certificate in my_certificates
        if days_until_expiry(certificate.valid_to, today) <= 90
    ][:8]

    upcoming_scheduled = list(
        db.scalars(
            select(Article)
            .where(Article.status == "scheduled", Article.scheduled_publish_at.is_not(None))
            .order_by(Article.scheduled_publish_at.asc())
            .limit(10)
        ).all()
    )

    recent_publications = list(
        db.scalars(select(Publication).order_by(Publication.created_at.desc()).limit(10)).all()
    )

    return {
        "greeting_name": user.get("name") or "",
        "my_drafts": [_article_summary(item) for item in my_drafts],
        "my_in_review": [_article_summary(item) for item in my_in_review],
        "my_approvals": approvals[:12],
        "my_expiring_certificates": my_expiring,
        "upcoming_scheduled": [_article_summary(item) for item in upcoming_scheduled],
        "recent_publications": [
            {
                "id": item.id,
                "title": item.title,
                "resource_type": item.resource_type,
                "resource_id": item.resource_id,
                "published_by_name": item.published_by_name,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in recent_publications
        ],
        "counts": {
            "my_drafts": len(my_drafts),
            "my_in_review": len(my_in_review),
            "my_approvals": len(approvals),
            "my_expiring": len(my_expiring),
            "upcoming_scheduled": len(upcoming_scheduled),
        },
    }


def build_publish_calendar(
    db: Session,
    *,
    days_ahead: int = 90,
    days_back: int = 14,
) -> dict[str, Any]:
    today = date.today()
    start = datetime.combine(today - timedelta(days=days_back), datetime.min.time(), tzinfo=timezone.utc)
    end_date = expiry_window_end(days_ahead, today)
    end = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    events: list[dict[str, Any]] = []

    scheduled = db.scalars(
        select(Article)
        .where(
            Article.status == "scheduled",
            Article.scheduled_publish_at.is_not(None),
            Article.scheduled_publish_at >= start,
            Article.scheduled_publish_at <= end,
        )
        .order_by(Article.scheduled_publish_at.asc())
    ).all()
    for article in scheduled:
        events.append(
            {
                "id": f"scheduled-{article.id}",
                "type": "scheduled_publish",
                "title": article.title or "Untitled",
                "date": article.scheduled_publish_at.date().isoformat() if article.scheduled_publish_at else today.isoformat(),
                "datetime": article.scheduled_publish_at.isoformat() if article.scheduled_publish_at else None,
                "resource_type": "article",
                "resource_id": article.id,
                "status": article.status,
            }
        )

    publications = db.scalars(
        select(Publication)
        .where(Publication.created_at >= start, Publication.created_at <= end)
        .order_by(Publication.created_at.desc())
        .limit(100)
    ).all()
    for publication in publications:
        if publication.resource_type == "certificate_reminder":
            event_type = "certificate_reminder"
        else:
            event_type = "publication"
        events.append(
            {
                "id": f"publication-{publication.id}",
                "type": event_type,
                "title": publication.title,
                "date": publication.created_at.date().isoformat() if publication.created_at else today.isoformat(),
                "datetime": publication.created_at.isoformat() if publication.created_at else None,
                "resource_type": publication.resource_type,
                "resource_id": publication.resource_id,
                "status": "sent",
            }
        )

    certificates = db.scalars(
        select(Certificate)
        .where(Certificate.valid_to >= today, Certificate.valid_to <= end_date)
        .order_by(Certificate.valid_to.asc())
    ).all()
    for certificate in certificates:
        events.append(
            {
                "id": f"expiry-{certificate.id}",
                "type": "certificate_expiry",
                "title": certificate.name,
                "date": certificate.valid_to.isoformat(),
                "datetime": None,
                "resource_type": "certificate",
                "resource_id": certificate.id,
                "status": compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress, today),
            }
        )

    events.sort(key=lambda item: (item["date"], item.get("datetime") or ""))
    by_date: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_date.setdefault(event["date"], []).append(event)

    return {
        "range": {
            "start": (today - timedelta(days=days_back)).isoformat(),
            "end": end_date.isoformat(),
        },
        "events": events,
        "by_date": by_date,
    }
