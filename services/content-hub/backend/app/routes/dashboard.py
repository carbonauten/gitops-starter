from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..certificates import expiry_window_end
from ..dashboard_service import build_home_dashboard, build_publish_calendar
from ..database import Article, Certificate, FileAsset, get_db
from ..dependencies import get_current_user
from ..outlook_service import fetch_outlook_calendar_events, outlook_status
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
    _user: dict = Depends(get_current_user),
) -> dict:
    today = date.today()
    drafts = db.scalar(select(func.count()).select_from(Article).where(Article.status == "draft")) or 0
    in_review = db.scalar(select(func.count()).select_from(Article).where(Article.status == "review")) or 0
    scheduled = db.scalar(select(func.count()).select_from(Article).where(Article.status == "scheduled")) or 0
    published = db.scalar(select(func.count()).select_from(Article).where(Article.status == "published")) or 0
    files = db.scalar(select(func.count()).select_from(FileAsset)) or 0
    certificates = db.scalar(select(func.count()).select_from(Certificate)) or 0
    renewals_pending = (
        db.scalar(
            select(func.count()).select_from(Certificate).where(Certificate.renewal_approval_status == "pending")
        )
        or 0
    )
    stats = DashboardStats(
        drafts=drafts,
        in_review=in_review,
        scheduled=scheduled,
        published=published,
        files=files,
        certificates=certificates,
        renewals_pending=renewals_pending,
        expiring_30=_count_expiring(db, 30, today),
        expiring_60=_count_expiring(db, 60, today),
        expiring_90=_count_expiring(db, 90, today),
    )
    return {"stats": stats}


@router.get("/home")
def dashboard_home(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return {"home": build_home_dashboard(db, user)}


@router.get("/calendar")
async def dashboard_calendar(
    days_ahead: int = Query(default=90, ge=7, le=180),
    days_back: int = Query(default=14, ge=0, le=60),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    user_id = user.get("db_id", "")
    calendar = build_publish_calendar(db, days_ahead=days_ahead, days_back=days_back)
    outlook = outlook_status(db, user_id=user_id)
    if outlook.get("connected"):
        outlook_events = await fetch_outlook_calendar_events(
            db,
            user_id=user_id,
            days_ahead=days_ahead,
            days_back=days_back,
        )
        if outlook_events:
            events = list(calendar["events"]) + outlook_events
            events.sort(key=lambda item: (item["date"], item.get("datetime") or ""))
            by_date: dict[str, list] = {}
            for event in events:
                by_date.setdefault(event["date"], []).append(event)
            calendar = {**calendar, "events": events, "by_date": by_date}
    return {"calendar": calendar, "outlook": outlook}
