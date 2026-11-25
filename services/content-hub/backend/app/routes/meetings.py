from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..meeting_service import create_meeting, list_recent_meetings
from ..schemas import MeetingCreateRequest

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("")
def meetings_list(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"meetings": list_recent_meetings(db)}


@router.post("")
def meetings_create(
    payload: MeetingCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return {"meeting": create_meeting(db, user=user, title=payload.title)}
