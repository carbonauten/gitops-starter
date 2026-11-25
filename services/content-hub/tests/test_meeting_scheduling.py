from datetime import datetime, timedelta, timezone

import pytest

from app.meeting_service import (
    build_ics,
    create_meeting,
    list_recent_meetings,
    list_upcoming_meetings,
    parse_attendee_emails,
    schedule_meeting,
)


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_parse_attendee_emails_filters_invalid_entries():
    raw = "anna@example.com, not-an-email ben@example.com;  , ,carl@example.com"
    assert parse_attendee_emails(raw) == ["anna@example.com", "ben@example.com", "carl@example.com"]


def test_parse_attendee_emails_empty_string():
    assert parse_attendee_emails("") == []


def test_schedule_meeting_appears_in_upcoming_not_recent(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    future = datetime.now(timezone.utc) + timedelta(days=1)
    meeting = schedule_meeting(db_session, user=user, title="Standup", scheduled_at=future, duration_minutes=45)

    assert meeting["scheduled_at"] is not None
    assert meeting["duration_minutes"] == 45
    assert meeting["ics_url"] == f"/api/meetings/{meeting['id']}/ics"

    upcoming = list_upcoming_meetings(db_session)
    assert any(m["id"] == meeting["id"] for m in upcoming)

    recent = list_recent_meetings(db_session)
    assert not any(m["id"] == meeting["id"] for m in recent)


def test_scheduled_meeting_in_the_past_counts_as_recent_not_upcoming(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    just_started = datetime.now(timezone.utc) - timedelta(minutes=5)
    meeting = schedule_meeting(db_session, user=user, title="Live now", scheduled_at=just_started, duration_minutes=30)

    recent = list_recent_meetings(db_session)
    assert any(m["id"] == meeting["id"] for m in recent)

    upcoming = list_upcoming_meetings(db_session)
    assert not any(m["id"] == meeting["id"] for m in upcoming)


def test_long_ended_scheduled_meeting_drops_out_of_recent(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    long_ago = datetime.now(timezone.utc) - timedelta(hours=5)
    meeting = schedule_meeting(db_session, user=user, title="Old", scheduled_at=long_ago, duration_minutes=30)

    recent = list_recent_meetings(db_session)
    assert not any(m["id"] == meeting["id"] for m in recent)


def test_instant_meeting_still_works_unaffected(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    meeting = create_meeting(db_session, user=user, title="Quick sync")
    assert meeting["scheduled_at"] is None
    recent = list_recent_meetings(db_session)
    assert any(m["id"] == meeting["id"] for m in recent)


def test_duration_is_clamped_to_sane_bounds(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    too_short = schedule_meeting(db_session, user=user, title="x", scheduled_at=future, duration_minutes=1)
    assert too_short["duration_minutes"] == 5
    too_long = schedule_meeting(db_session, user=user, title="y", scheduled_at=future, duration_minutes=10000)
    assert too_long["duration_minutes"] == 8 * 60


def test_build_ics_contains_expected_fields(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    future = datetime.now(timezone.utc) + timedelta(days=2)
    meeting_dict = schedule_meeting(db_session, user=user, title="Planning", scheduled_at=future, duration_minutes=60)
    from app.meeting_service import get_meeting

    meeting = get_meeting(db_session, meeting_id=meeting_dict["id"])
    ics = build_ics(meeting, organizer_email="mike@example.com", organizer_name="Mike").decode("utf-8")

    assert "BEGIN:VCALENDAR" in ics
    assert "SUMMARY:Planning" in ics
    assert "ORGANIZER;CN=Mike:mailto:mike@example.com" in ics
    assert meeting.room_name in ics
    assert ics.endswith("END:VCALENDAR\r\n")
