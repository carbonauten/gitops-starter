from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..dependencies import get_current_user, require_editor
from ..database import Article, get_db
from ..i18n import normalize_language
from ..roles import ARTICLE_STATUSES, EDITABLE_ARTICLE_STATUSES
from ..schemas import ArticleCreate, ArticleResponse, ArticleUpdate
from ..templates import get_template, list_templates

router = APIRouter(prefix="/api/articles", tags=["articles"])


def _to_response(article: Article) -> ArticleResponse:
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


@router.get("/templates")
def article_templates(request: Request) -> dict:
    language = normalize_language(getattr(request.state, "language", "en"))
    return {"templates": list_templates(language)}


@router.get("/templates/{template_id}")
def article_template(template_id: str, request: Request) -> dict:
    language = normalize_language(getattr(request.state, "language", "en"))
    template = get_template(template_id, language)
    if not template:
        raise HTTPException(status_code=404, detail="not_found")
    return {"template": template}


@router.get("")
def list_articles(
    q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    stmt = select(Article).order_by(Article.updated_at.desc())
    if status in ARTICLE_STATUSES:
        stmt = stmt.where(Article.status == status)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Article.title.ilike(pattern), Article.content.ilike(pattern)))
    articles = db.scalars(stmt).all()
    return {"articles": [_to_response(article) for article in articles]}


@router.post("", status_code=201)
def create_article(
    payload: ArticleCreate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    article = Article(
        title=payload.title,
        content=payload.content,
        status="draft",
        template=payload.template,
        author_id=user["id"],
        author_name=user["name"],
        author_email=user.get("email", ""),
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action="create",
        actor=user,
        details={"title": article.title, "status": article.status},
    )
    return {"article": _to_response(article)}


@router.get("/{article_id}")
def get_article(
    article_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    return {"article": _to_response(article)}


@router.patch("/{article_id}")
def update_article(
    article_id: str,
    payload: ArticleUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    if article.status not in EDITABLE_ARTICLE_STATUSES:
        raise HTTPException(status_code=400, detail="invalid_workflow_state")

    if payload.title is not None:
        article.title = payload.title
    if payload.content is not None:
        article.content = payload.content

    db.commit()
    db.refresh(article)
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action="update",
        actor=user,
        details={"title": article.title, "status": article.status},
    )
    return {"article": _to_response(article)}


@router.delete("/{article_id}", status_code=204)
def delete_article(
    article_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="not_found")
    log_audit(
        db,
        entity_type="article",
        entity_id=article.id,
        action="delete",
        actor=user,
        details={"title": article.title, "status": article.status},
    )
    db.delete(article)
    db.commit()
    return Response(status_code=204)
