from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app import caldav_client, mailbox_org_service


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- connect / disconnect / status -----------------------------------------


def test_connect_requires_email_and_password(db_session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="", password="x")
    with pytest.raises(HTTPException):
        mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="a@mailbox.org", password="")


def test_connect_saves_integration_when_login_succeeds(db_session, monkeypatch):
    monkeypatch.setattr(mailbox_org_service, "test_connection", lambda **kwargs: None)

    status = mailbox_org_service.connect_mailbox_org(
        db_session, user_id="u1", email="anna@mailbox.org", password="app-pass"
    )
    assert status["connected"] is True
    assert status["account"] == "anna@mailbox.org"

    again = mailbox_org_service.mailbox_org_status(db_session, user_id="u1")
    assert again["connected"] is True


def test_connect_surfaces_login_failure(db_session, monkeypatch):
    from fastapi import HTTPException

    def _fail(**kwargs):
        raise HTTPException(status_code=502, detail="imap_connect_failed")

    monkeypatch.setattr(mailbox_org_service, "test_connection", _fail)

    with pytest.raises(HTTPException) as exc_info:
        mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="anna@mailbox.org", password="wrong")
    assert exc_info.value.detail == "mailbox_org_login_failed"

    status = mailbox_org_service.mailbox_org_status(db_session, user_id="u1")
    assert status["connected"] is False


def test_disconnect_removes_integration(db_session, monkeypatch):
    monkeypatch.setattr(mailbox_org_service, "test_connection", lambda **kwargs: None)
    mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="anna@mailbox.org", password="x")
    mailbox_org_service.disconnect_mailbox_org(db_session, user_id="u1")
    assert mailbox_org_service.mailbox_org_status(db_session, user_id="u1")["connected"] is False


# --- routes -------------------------------------------------------------


def test_mailbox_org_status_route_requires_login(client):
    response = client.get("/api/integrations/mailbox-org/status")
    assert response.status_code == 401


def test_mailbox_org_connect_route(auth_client, monkeypatch):
    monkeypatch.setattr(mailbox_org_service, "test_connection", lambda **kwargs: None)
    response = auth_client.post(
        "/api/integrations/mailbox-org/connect",
        json={"email": "anna@mailbox.org", "password": "app-pass"},
    )
    assert response.status_code == 200
    assert response.json()["connected"] is True


# --- ICS building ---------------------------------------------------------


def test_build_invite_ics_contains_attendees_and_method():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    ics = mailbox_org_service._build_invite_ics(
        uid="abc@carbonauten",
        method="REQUEST",
        title="Sync",
        start=start,
        end=end,
        location="https://meet.jit.si/carbonauten-x",
        description="join",
        organizer_email="mike@mailbox.org",
        organizer_name="Mike",
        attendee_emails=["anna@example.com", "ben@example.com"],
    ).decode("utf-8")

    assert "METHOD:REQUEST" in ics
    assert "ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE;CN=anna@example.com:mailto:anna@example.com" in ics
    assert "ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE;CN=ben@example.com:mailto:ben@example.com" in ics
    assert "ORGANIZER;CN=Mike:mailto:mike@mailbox.org" in ics


# --- CalDAV discovery -----------------------------------------------------


class _FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


PRINCIPAL_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:propstat>
      <d:prop><d:current-user-principal><d:href>/principals/anna/</d:href></d:current-user-principal></d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>"""

HOME_SET_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:propstat>
      <d:prop><c:calendar-home-set><d:href>/calendars/anna/</d:href></c:calendar-home-set></d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>"""

HOME_LISTING_XML = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:response>
    <d:href>/calendars/anna/</d:href>
    <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
  </d:response>
  <d:response>
    <d:href>/calendars/anna/Calendar/</d:href>
    <d:propstat>
      <d:prop><d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Calendar</d:displayname></d:prop>
    </d:propstat>
  </d:response>
</d:multistatus>"""


def test_discover_calendar_url_happy_path(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        if url == "https://dav.mailbox.org/":
            return _FakeResponse(207, PRINCIPAL_XML)
        if url == "https://dav.mailbox.org/principals/anna/":
            return _FakeResponse(207, HOME_SET_XML)
        if url == "https://dav.mailbox.org/calendars/anna/":
            return _FakeResponse(207, HOME_LISTING_XML)
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(caldav_client.httpx, "request", fake_request)
    result = caldav_client.discover_calendar_url(
        "https://dav.mailbox.org/", username="anna@mailbox.org", password="pw"
    )
    assert result == "https://dav.mailbox.org/calendars/anna/Calendar/"
    assert len(calls) == 3


def test_discover_calendar_url_returns_none_on_network_error(monkeypatch):
    import httpx

    def fake_request(method, url, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(caldav_client.httpx, "request", fake_request)
    assert caldav_client.discover_calendar_url("https://dav.mailbox.org/", username="a", password="b") is None


def test_create_event_puts_ics(monkeypatch):
    captured = {}

    def fake_put(url, **kwargs):
        captured["url"] = url
        captured["content"] = kwargs.get("content")
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(caldav_client.httpx, "put", fake_put)
    ok = caldav_client.create_event(
        "https://dav.mailbox.org/calendars/anna/Calendar/",
        username="anna@mailbox.org",
        password="pw",
        ics=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
        uid="event-1",
    )
    assert ok is True
    assert captured["url"] == "https://dav.mailbox.org/calendars/anna/Calendar/event-1.ics"


# --- send_meeting_invite ---------------------------------------------------


def test_send_meeting_invite_false_when_not_connected(db_session):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    result = mailbox_org_service.send_meeting_invite(
        db_session,
        user_id="nobody",
        organizer_name="Mike",
        title="x",
        start=start,
        end=start + timedelta(hours=1),
        meeting_url="https://meet.jit.si/x",
        attendee_emails=["a@example.com"],
    )
    assert result is False


def test_send_meeting_invite_sends_email_when_attendees_present(db_session, monkeypatch):
    monkeypatch.setattr(mailbox_org_service, "test_connection", lambda **kwargs: None)
    mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="anna@mailbox.org", password="app-pass")

    monkeypatch.setattr(caldav_client, "discover_calendar_url", lambda *a, **kw: "https://dav.mailbox.org/cal/")
    monkeypatch.setattr(caldav_client, "create_event", lambda *a, **kw: True)

    sent_messages = []

    class _FakeSmtp:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            assert user == "anna@mailbox.org"

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setattr(mailbox_org_service.smtplib, "SMTP", _FakeSmtp)

    start = datetime.now(timezone.utc) + timedelta(days=1)
    result = mailbox_org_service.send_meeting_invite(
        db_session,
        user_id="u1",
        organizer_name="Anna",
        title="Planning",
        start=start,
        end=start + timedelta(hours=1),
        meeting_url="https://meet.jit.si/carbonauten-x",
        attendee_emails=["ben@example.com"],
    )
    assert result is True
    assert len(sent_messages) == 1
    assert sent_messages[0]["To"] == "ben@example.com"


def test_send_meeting_invite_without_attendees_only_writes_calendar(db_session, monkeypatch):
    monkeypatch.setattr(mailbox_org_service, "test_connection", lambda **kwargs: None)
    mailbox_org_service.connect_mailbox_org(db_session, user_id="u1", email="anna@mailbox.org", password="app-pass")

    create_event_calls = []
    monkeypatch.setattr(caldav_client, "discover_calendar_url", lambda *a, **kw: "https://dav.mailbox.org/cal/")
    monkeypatch.setattr(
        caldav_client, "create_event", lambda *a, **kw: create_event_calls.append(1) or True
    )

    start = datetime.now(timezone.utc) + timedelta(days=1)
    result = mailbox_org_service.send_meeting_invite(
        db_session,
        user_id="u1",
        organizer_name="Anna",
        title="Solo block",
        start=start,
        end=start + timedelta(hours=1),
        meeting_url="https://meet.jit.si/carbonauten-x",
        attendee_emails=[],
    )
    assert result is False
    assert create_event_calls == [1]
