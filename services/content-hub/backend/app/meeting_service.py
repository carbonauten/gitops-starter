from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .database import Meeting

logger = logging.getLogger(__name__)

# meet.jit.si is Jitsi's free, public instance: no server-side auth needed,
# anyone with the room URL can join. Room names live in a global namespace,
# so a distinctive prefix avoids accidentally colliding with a stranger's
# room. Self-hosting Jitsi instead would need its own infrastructure (prosody
# + jicofo + jvb + web) - not done here, see services/README for the
# tradeoff if private hosting becomes a requirement.
JITSI_DOMAIN = "meet.jit.si"
ROOM_PREFIX = "carbonauten-"
RECENT_WINDOW_HOURS = 12
LIVE_GRACE_MINUTES = 15  # a scheduled call still shows as "live" a bit past its nominal end
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _as_utc(value: datetime) -> datetime:
    """SQLite (used in tests/dev) doesn't round-trip tzinfo through
    DateTime(timezone=True), so a value read back from the DB can come back
    naive even though we stored it as UTC-aware - normalize before any
    comparison/arithmetic against a tz-aware "now"."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _new_room_name() -> str:
    return f"{ROOM_PREFIX}{secrets.token_hex(5)}"


def meeting_url(room_name: str) -> str:
    return f"https://{JITSI_DOMAIN}/{room_name}"


def _serialize(meeting: Meeting) -> dict[str, Any]:
    return {
        "id": meeting.id,
        "room_name": meeting.room_name,
        "title": meeting.title,
        "created_by_name": meeting.created_by_name,
        "created_at": _as_utc(meeting.created_at).isoformat() if meeting.created_at else None,
        "scheduled_at": _as_utc(meeting.scheduled_at).isoformat() if meeting.scheduled_at else None,
        "duration_minutes": meeting.duration_minutes,
        "url": meeting_url(meeting.room_name),
        "domain": JITSI_DOMAIN,
        "ics_url": f"/api/meetings/{meeting.id}/ics",
    }


def create_meeting(db: Session, *, user: dict[str, Any], title: str = "") -> dict[str, Any]:
    meeting = Meeting(
        room_name=_new_room_name(),
        title=(title or "").strip()[:300],
        created_by_id=str(user.get("db_id") or user.get("id") or ""),
        created_by_name=str(user.get("name") or "User"),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize(meeting)


def parse_attendee_emails(raw: str) -> list[str]:
    candidates = re.split(r"[,;\s]+", (raw or "").strip())
    return [email for email in candidates if EMAIL_RE.match(email)]


def schedule_meeting(
    db: Session,
    *,
    user: dict[str, Any],
    title: str,
    scheduled_at: datetime,
    duration_minutes: int = 30,
) -> dict[str, Any]:
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    duration = max(5, min(int(duration_minutes or 30), 8 * 60))

    meeting = Meeting(
        room_name=_new_room_name(),
        title=(title or "").strip()[:300] or "Meeting",
        created_by_id=str(user.get("db_id") or user.get("id") or ""),
        created_by_name=str(user.get("name") or "User"),
        scheduled_at=scheduled_at,
        duration_minutes=duration,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return _serialize(meeting)


def get_meeting(db: Session, *, meeting_id: str) -> Meeting:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="not_found")
    return meeting


def list_recent_meetings(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    """Instant calls, plus scheduled meetings whose time has already arrived
    - i.e. everything that's plausibly joinable right now."""
    now = datetime.now(timezone.utc)
    instant_cutoff = now - timedelta(hours=RECENT_WINDOW_HOURS)
    scheduled_lookback = now - timedelta(days=1)

    rows = db.scalars(
        select(Meeting)
        .where(
            or_(
                and_(Meeting.scheduled_at.is_(None), Meeting.created_at >= instant_cutoff),
                and_(Meeting.scheduled_at.isnot(None), Meeting.scheduled_at >= scheduled_lookback, Meeting.scheduled_at <= now),
            )
        )
        .order_by(Meeting.created_at.desc())
    ).all()

    live: list[Meeting] = []
    for row in rows:
        if row.scheduled_at is None:
            live.append(row)
            continue
        ends_at = _as_utc(row.scheduled_at) + timedelta(minutes=(row.duration_minutes or 30) + LIVE_GRACE_MINUTES)
        if ends_at >= now:
            live.append(row)

    return [_serialize(row) for row in live[:limit]]


def list_upcoming_meetings(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Meeting)
        .where(Meeting.scheduled_at.isnot(None), Meeting.scheduled_at > now)
        .order_by(Meeting.scheduled_at.asc())
        .limit(limit)
    ).all()
    return [_serialize(row) for row in rows]


def _ics_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ics_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(meeting: Meeting, *, organizer_email: str, organizer_name: str) -> bytes:
    raw_start = meeting.scheduled_at or meeting.created_at or datetime.now(timezone.utc)
    start = _as_utc(raw_start)
    end = start + timedelta(minutes=meeting.duration_minutes or 30)
    url = meeting_url(meeting.room_name)
    description = f"Jitsi-Meeting beitreten: {url}"
    organizer_email = organizer_email or "no-reply@carbonauten.com"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Unified Carbonauten Platform//Meetings//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{meeting.id}@carbonauten",
        f"DTSTAMP:{_ics_datetime(datetime.now(timezone.utc))}",
        f"DTSTART:{_ics_datetime(start)}",
        f"DTEND:{_ics_datetime(end)}",
        f"SUMMARY:{_ics_escape(meeting.title or 'Meeting')}",
        f"DESCRIPTION:{_ics_escape(description)}",
        f"LOCATION:{_ics_escape(url)}",
        f"ORGANIZER;CN={_ics_escape(organizer_name or 'Organizer')}:mailto:{organizer_email}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
