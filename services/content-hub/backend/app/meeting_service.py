from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Meeting

# meet.jit.si is Jitsi's free, public instance: no server-side auth needed,
# anyone with the room URL can join. Room names live in a global namespace,
# so a distinctive prefix avoids accidentally colliding with a stranger's
# room. Self-hosting Jitsi instead would need its own infrastructure (prosody
# + jicofo + jvb + web) - not done here, see services/README for the
# tradeoff if private hosting becomes a requirement.
JITSI_DOMAIN = "meet.jit.si"
ROOM_PREFIX = "carbonauten-"
RECENT_WINDOW_HOURS = 12


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
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        "url": meeting_url(meeting.room_name),
        "domain": JITSI_DOMAIN,
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


def list_recent_meetings(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_WINDOW_HOURS)
    rows = db.scalars(
        select(Meeting)
        .where(Meeting.created_at >= cutoff)
        .order_by(Meeting.created_at.desc())
        .limit(limit)
    ).all()
    return [_serialize(row) for row in rows]
