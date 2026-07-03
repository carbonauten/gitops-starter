from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_approver, require_cert_approver, require_editor
from ..schemas import ArticleResponse, CertificateResponse
from ..workflow_service import (
    approve_article,
    approve_certificate_renewal,
    article_to_workflow_dict,
    certificate_renewal_to_dict,
    list_pending_workflow,
    reject_article,
    reject_certificate_renewal,
    request_certificate_renewal,
    submit_article_for_review,
)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


class ApproveArticleRequest(BaseModel):
    scheduled_publish_at: Optional[datetime] = None


class RejectRequest(BaseModel):
    comment: str = Field(default="", max_length=2000)


def _article_response(article) -> ArticleResponse:
    return ArticleResponse(
        id=article.id,
        title=article.title,
        content=article.content,
        status=article.status,
        template=article.template,
        scheduled_publish_at=article.scheduled_publish_at,
        review_comment=article.review_comment,
        author_id=article.author_id,
        author_name=article.author_name,
        author_email=article.author_email,
        created_at=article.created_at,
        updated_at=article.updated_at,
    )


@router.get("/pending")
def pending_workflow(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return list_pending_workflow(db)


@router.post("/articles/{article_id}/submit")
def submit_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    article = submit_article_for_review(db, article_id, user)
    return {"article": _article_response(article)}


@router.post("/articles/{article_id}/approve")
def approve_article_route(
    article_id: str,
    payload: ApproveArticleRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_approver),
) -> dict:
    article = approve_article(
        db,
        article_id,
        user,
        scheduled_publish_at=payload.scheduled_publish_at,
    )
    return {"article": _article_response(article)}


@router.post("/articles/{article_id}/reject")
def reject_article_route(
    article_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_approver),
) -> dict:
    article = reject_article(db, article_id, user, comment=payload.comment)
    return {"article": _article_response(article)}


@router.post("/certificates/{certificate_id}/request-renewal")
def request_renewal_route(
    certificate_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    certificate = request_certificate_renewal(db, certificate_id, user)
    return {"certificate": certificate_renewal_to_dict(certificate)}


@router.post("/certificates/{certificate_id}/approve-renewal")
def approve_renewal_route(
    certificate_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_cert_approver),
) -> dict:
    certificate = approve_certificate_renewal(db, certificate_id, user)
    return {"certificate": certificate_renewal_to_dict(certificate)}


@router.post("/certificates/{certificate_id}/reject-renewal")
def reject_renewal_route(
    certificate_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_cert_approver),
) -> dict:
    certificate = reject_certificate_renewal(db, certificate_id, user, comment=payload.comment)
    return {"certificate": certificate_renewal_to_dict(certificate)}
