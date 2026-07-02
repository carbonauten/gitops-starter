from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..database import Article, FileAsset, get_db
from ..schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_user),
) -> dict:
    drafts = db.scalar(select(func.count()).select_from(Article).where(Article.status == "draft")) or 0
    published = db.scalar(select(func.count()).select_from(Article).where(Article.status == "published")) or 0
    files = db.scalar(select(func.count()).select_from(FileAsset)) or 0
    stats = DashboardStats(
        drafts=drafts,
        published=published,
        files=files,
        certificates=0,
    )
    return {"stats": stats}
