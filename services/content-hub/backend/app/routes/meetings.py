from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..meeting_service import (
    build_ics,
    create_meeting,
    get_meeting,
    list_recent_meetings,
    list_upcoming_meetings,
    meeting_url,
    parse_attendee_emails,
    schedule_meeting,
)
from ..outlook_service import create_outlook_calendar_event
from ..schemas import MeetingCreateRequest, MeetingScheduleRequest

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


@router.get("")
def meetings_list(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"meetings": list_recent_meetings(db)}


@router.get("/upcoming")
def meetings_upcoming(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"meetings": list_upcoming_meetings(db)}


@router.post("")
def meetings_create(
    payload: MeetingCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    return {"meeting": create_meeting(db, user=user, title=payload.title)}


@router.post("/schedule")
async def meetings_schedule(
    payload: MeetingScheduleRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    meeting = schedule_meeting(
        db,
        user=user,
        title=payload.title,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
    )
    attendee_emails = parse_attendee_emails(payload.attendees)

    outlook_invited = False
    if attendee_emails:
        row = get_meeting(db, meeting_id=meeting["id"])
        outlook_invited = await create_outlook_calendar_event(
            db,
            user_id=str(user.get("db_id") or ""),
            subject=meeting["title"],
            start=payload.scheduled_at,
            end=payload.scheduled_at + timedelta(minutes=payload.duration_minutes),
            body_html=f'<p>Jitsi-Meeting beitreten: <a href="{meeting_url(row.room_name)}">{meeting_url(row.room_name)}</a></p>',
            location=meeting_url(row.room_name),
            attendee_emails=attendee_emails,
        )

    return {
        "meeting": meeting,
        "attendee_emails": attendee_emails,
        "outlook_invited": outlook_invited,
    }


@router.get("/{meeting_id}/ics")
def meetings_ics(
    meeting_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> Response:
    meeting = get_meeting(db, meeting_id=meeting_id)
    content = build_ics(
        meeting,
        organizer_email=str(user.get("email") or ""),
        organizer_name=str(user.get("name") or ""),
    )
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{meeting.room_name}.ics"'},
    )
