from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..dependencies import get_current_user
from ..database import Article, Certificate, FileAsset, get_db
from ..schemas import SearchResult

router = APIRouter(prefix="/api/search", tags=["search"])


def _snippet(text: str, query: str, max_len: int = 140) -> str:
    cleaned = " ".join(text.replace("<", " ").replace(">", " ").split())
    if not cleaned:
        return ""
    lower = cleaned.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return cleaned[:max_len]
    start = max(0, idx - 40)
    return cleaned[start : start + max_len]


@router.get("")
def search(
    q: str = Query(min_length=1),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    pattern = f"%{q.strip()}%"
    articles = db.scalars(
        select(Article)
        .where(or_(Article.title.ilike(pattern), Article.content.ilike(pattern)))
        .order_by(Article.updated_at.desc())
        .limit(20)
    ).all()
    files = db.scalars(
        select(FileAsset)
        .where(or_(FileAsset.original_name.ilike(pattern), FileAsset.folder.ilike(pattern)))
        .order_by(FileAsset.created_at.desc())
        .limit(20)
    ).all()
    certificates = db.scalars(
        select(Certificate)
        .where(
            or_(
                Certificate.name.ilike(pattern),
                Certificate.issuer.ilike(pattern),
                Certificate.responsible_name.ilike(pattern),
            )
        )
        .order_by(Certificate.updated_at.desc())
        .limit(20)
    ).all()

    results: list[SearchResult] = []
    for article in articles:
        results.append(
            SearchResult(
                type="article",
                id=article.id,
                title=article.title or "Untitled",
                snippet=_snippet(article.content, q),
                status=article.status,
                updated_at=article.updated_at,
            )
        )
    for file_asset in files:
        results.append(
            SearchResult(
                type="file",
                id=file_asset.id,
                title=file_asset.original_name,
                snippet=file_asset.folder,
                folder=file_asset.folder,
                updated_at=file_asset.created_at,
            )
        )
    for certificate in certificates:
        results.append(
            SearchResult(
                type="certificate",
                id=certificate.id,
                title=certificate.name,
                snippet=certificate.issuer or certificate.category,
                status=certificate.category,
                updated_at=certificate.updated_at,
            )
        )

    results.sort(key=lambda item: item.updated_at, reverse=True)
    return {"query": q, "results": results}


@router.get("/folders")
def list_folders(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    folders = db.scalars(select(FileAsset.folder).distinct().order_by(FileAsset.folder)).all()
    return {"folders": folders}
