import pytest

from app.meeting_service import ROOM_PREFIX, _new_room_name, create_meeting, list_recent_meetings, meeting_url


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_new_room_name_has_distinctive_prefix_and_is_unique():
    first = _new_room_name()
    second = _new_room_name()
    assert first.startswith(ROOM_PREFIX)
    assert first != second


def test_meeting_url_points_at_public_jitsi_instance():
    assert meeting_url("carbonauten-abc123") == "https://meet.jit.si/carbonauten-abc123"


def test_create_and_list_recent_meetings(db_session):
    user = {"db_id": "user-1", "name": "Mike"}
    meeting = create_meeting(db_session, user=user, title="Standup")

    assert meeting["title"] == "Standup"
    assert meeting["created_by_name"] == "Mike"
    assert meeting["url"] == meeting_url(meeting["room_name"])

    recent = list_recent_meetings(db_session)
    assert any(m["id"] == meeting["id"] for m in recent)


def test_meetings_routes_require_login(client):
    response = client.get("/api/meetings")
    assert response.status_code == 401


def test_meetings_create_and_list_via_api(auth_client):
    created = auth_client.post("/api/meetings", json={"title": "Sync"})
    assert created.status_code == 200
    room_name = created.json()["meeting"]["room_name"]

    listed = auth_client.get("/api/meetings")
    assert listed.status_code == 200
    rooms = [m["room_name"] for m in listed.json()["meetings"]]
    assert room_name in rooms
