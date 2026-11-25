from datetime import datetime, timedelta, timezone


def test_schedule_meeting_via_api_without_attendees(auth_client):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = auth_client.post(
        "/api/meetings/schedule",
        json={"title": "Planning", "scheduled_at": future, "duration_minutes": 30, "attendees": ""},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["meeting"]["title"] == "Planning"
    assert payload["attendee_emails"] == []
    assert payload["outlook_invited"] is False


def test_scheduled_meeting_appears_in_upcoming_endpoint(auth_client):
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    created = auth_client.post(
        "/api/meetings/schedule",
        json={"title": "Review", "scheduled_at": future, "duration_minutes": 45, "attendees": ""},
    )
    meeting_id = created.json()["meeting"]["id"]

    upcoming = auth_client.get("/api/meetings/upcoming")
    assert upcoming.status_code == 200
    ids = [m["id"] for m in upcoming.json()["meetings"]]
    assert meeting_id in ids


def test_download_ics_for_scheduled_meeting(auth_client):
    future = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    created = auth_client.post(
        "/api/meetings/schedule",
        json={"title": "Board Meeting", "scheduled_at": future, "duration_minutes": 60, "attendees": ""},
    )
    meeting_id = created.json()["meeting"]["id"]

    ics_response = auth_client.get(f"/api/meetings/{meeting_id}/ics")
    assert ics_response.status_code == 200
    assert ics_response.headers["content-type"].startswith("text/calendar")
    assert b"SUMMARY:Board Meeting" in ics_response.content


def test_schedule_meeting_requires_login(client):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = client.post(
        "/api/meetings/schedule",
        json={"title": "x", "scheduled_at": future, "duration_minutes": 30, "attendees": ""},
    )
    assert response.status_code == 401


def test_schedule_meeting_rejects_invalid_duration(auth_client):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    response = auth_client.post(
        "/api/meetings/schedule",
        json={"title": "x", "scheduled_at": future, "duration_minutes": 0, "attendees": ""},
    )
    assert response.status_code == 422
