from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit_service import log_audit
from .database import Article, Certificate
from .roles import EDITABLE_ARTICLE_STATUSES

logger = logging.getLogger(__name__)


def _normalize_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def article_to_workflow_dict(article: Article) -> dict:
    return {
        "id": article.id,
        "title": article.title,
        "status": article.status,
        "author_name": article.author_name,
        "scheduled_publish_at": article.scheduled_publish_at.isoformat() if article.scheduled_publish_at else None,
        "review_comment": article.review_comment,
        "updated_at": article.updated_at.isoformat(),
    }


def certificate_renewal_to_dict(certificate: Certificate) -> dict:
    return {
        "id": certificate.id,
        "name": certificate.name,
        "renewal_in_progress": certificate.renewal_in_progress,
        "renewal_approval_status": certificate.renewal_approval_status,
        "renewal_review_comment": certificate.renewal_review_comment,
        "responsible_name": certificate.responsible_name,
        "updated_at": certificate.updated_at.isoformat(),
    }


def list_pending_workflow(db: Session) -> dict:
    articles = list(
        db.scalars(select(Article).where(Article.status == "review").order_by(Article.updated_at.desc())).all()
    )
    scheduled = list(
        db.scalars(select(Article).where(Article.status == "scheduled").order_by(Article.scheduled_publish_at)).all()
    )
    renewals = list(
        db.scalars(
            select(Certificate)
            .where(Certificate.renewal_approval_status == "pending")
            .order_by(Certificate.updated_at.desc())
        ).all()
    )
    return {
        "articles_in_review": [article_to_workflow_dict(article) for article in articles],
        "articles_scheduled": [article_to_workflow_dict(article) for article in scheduled],
        "certificate_renewals_pending": [certificate_renewal_to_dict(certificate) for certificate in renewals],
    }


def submit_article_for_review(db: Session, article_id: str, user: dict) -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    if article.status not in EDITABLE_ARTICLE_STATUSES:
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    article.status = "review"
    article.review_comment = ""
    db.commit()
    db.refresh(article)
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action="submit_review",
        actor=user,
        details={"title": article.title},
    )
    return article


def approve_article(
    db: Session,
    article_id: str,
    user: dict,
    *,
    scheduled_publish_at: Optional[datetime] = None,
) -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    if article.status != "review":
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    scheduled_at = _normalize_utc(scheduled_publish_at)
    now = datetime.now(timezone.utc)
    if scheduled_at and scheduled_at > now:
        article.status = "scheduled"
        article.scheduled_publish_at = scheduled_at
        action = "schedule_publish"
    else:
        article.status = "published"
        article.scheduled_publish_at = None
        action = "approve_publish"

    article.review_comment = ""
    db.commit()
    db.refresh(article)
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action=action,
        actor=user,
        details={
            "title": article.title,
            "scheduled_publish_at": article.scheduled_publish_at.isoformat() if article.scheduled_publish_at else None,
        },
    )
    return article


def reject_article(db: Session, article_id: str, user: dict, *, comment: str = "") -> Article:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    if article.status != "review":
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    article.status = "rejected"
    article.review_comment = comment.strip()
    article.scheduled_publish_at = None
    db.commit()
    db.refresh(article)
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action="reject_review",
        actor=user,
        details={"title": article.title, "comment": article.review_comment},
    )
    return article


def request_certificate_renewal(db: Session, certificate_id: str, user: dict) -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")
    if not certificate.renewal_in_progress:
        raise HTTPException(status_code=400, detail="renewal_not_requested")

    certificate.renewal_approval_status = "pending"
    certificate.renewal_review_comment = ""
    db.commit()
    db.refresh(certificate)
    log_audit(
        db,
        entity_type="certificate",
        entity_id=certificate.id,
        action="request_renewal_approval",
        actor=user,
        details={"name": certificate.name},
    )
    return certificate


def approve_certificate_renewal(db: Session, certificate_id: str, user: dict) -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")
    if certificate.renewal_approval_status != "pending":
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    certificate.renewal_approval_status = "approved"
    certificate.renewal_review_comment = ""
    db.commit()
    db.refresh(certificate)
    log_audit(
        db,
        entity_type="certificate",
        entity_id=certificate.id,
        action="approve_renewal",
        actor=user,
        details={"name": certificate.name},
    )
    return certificate


def reject_certificate_renewal(db: Session, certificate_id: str, user: dict, *, comment: str = "") -> Certificate:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="not_found")
    if certificate.renewal_approval_status != "pending":
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    certificate.renewal_approval_status = "rejected"
    certificate.renewal_review_comment = comment.strip()
    certificate.renewal_in_progress = False
    db.commit()
    db.refresh(certificate)
    log_audit(
        db,
        entity_type="certificate",
        entity_id=certificate.id,
        action="reject_renewal",
        actor=user,
        details={"name": certificate.name, "comment": certificate.renewal_review_comment},
    )
    return certificate


def process_due_scheduled_articles(db: Session) -> int:
    now = datetime.now(timezone.utc)
    articles = list(
        db.scalars(
            select(Article).where(
                Article.status == "scheduled",
                Article.scheduled_publish_at.is_not(None),
                Article.scheduled_publish_at <= now,
            )
        ).all()
    )
    published = 0
    for article in articles:
        article.status = "published"
        article.scheduled_publish_at = None
        published += 1
        log_audit(
            db,
            entity_type="article",
            entity_id=article.id,
            action="scheduled_publish",
            actor={"id": "system", "name": "Scheduler", "email": ""},
            details={"title": article.title},
        )
    if published:
        db.commit()
        logger.info("Published %s scheduled article(s)", published)
    return published
