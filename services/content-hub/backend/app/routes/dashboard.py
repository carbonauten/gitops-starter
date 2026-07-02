from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..database import Article, Certificate, FileAsset, get_db
from ..certificates import expiry_window_end
from ..schemas import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


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


@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_user),
) -> dict:
    today = date.today()
    drafts = db.scalar(select(func.count()).select_from(Article).where(Article.status == "draft")) or 0
    published = db.scalar(select(func.count()).select_from(Article).where(Article.status == "published")) or 0
    files = db.scalar(select(func.count()).select_from(FileAsset)) or 0
    certificates = db.scalar(select(func.count()).select_from(Certificate)) or 0
    stats = DashboardStats(
        drafts=drafts,
        published=published,
        files=files,
        certificates=certificates,
        expiring_30=_count_expiring(db, 30, today),
        expiring_60=_count_expiring(db, 60, today),
        expiring_90=_count_expiring(db, 90, today),
    )
    return {"stats": stats}
