from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..analytics_service import build_analytics_overview
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def analytics_overview(
    days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"overview": build_analytics_overview(db, days=days)}
