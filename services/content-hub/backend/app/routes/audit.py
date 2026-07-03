from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit_service import list_audit_entries
from ..database import get_db
from ..dependencies import get_current_user, require_it_master

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def get_audit_log(
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    entries = list_audit_entries(db, entity_type=entity_type, entity_id=entity_id, limit=limit)
    return {"entries": entries}
