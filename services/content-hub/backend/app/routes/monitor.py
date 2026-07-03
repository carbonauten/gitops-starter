from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit_service import list_audit_entries
from ..config import get_settings
from ..database import Article, AuditLog, Certificate, FileAsset, SyncLog, get_db
from ..dependencies import require_it_master
from ..sync_service import sync_status
from ..certificates import expiry_window_end
from datetime import date

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/summary")
def monitor_summary(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    settings = get_settings()
    today = date.today()
    audit_count = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    last_sync = db.scalar(select(SyncLog).order_by(SyncLog.created_at.desc()).limit(1))
    expiring_30 = (
        db.scalar(
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.valid_to >= today,
                Certificate.valid_to <= expiry_window_end(30, today),
            )
        )
        or 0
    )
    return {
        "status": "ok",
        "deployment_region": settings.deployment_region,
        "email_provider": settings.email_provider,
        "publish_mock_mode": settings.publish_mock_mode,
        "sync": sync_status(db, settings),
        "articles_in_review": db.scalar(select(func.count()).select_from(Article).where(Article.status == "review")) or 0,
        "articles_scheduled": db.scalar(select(func.count()).select_from(Article).where(Article.status == "scheduled")) or 0,
        "renewals_pending": db.scalar(
            select(func.count()).select_from(Certificate).where(Certificate.renewal_approval_status == "pending")
        )
        or 0,
        "certificates_expiring_30": expiring_30,
        "file_count": db.scalar(select(func.count()).select_from(FileAsset)) or 0,
        "audit_entry_count": audit_count,
        "recent_audit": list_audit_entries(db, limit=10),
        "last_sync_status": last_sync.status if last_sync else None,
        "last_sync_at": last_sync.created_at.isoformat() if last_sync else None,
    }
