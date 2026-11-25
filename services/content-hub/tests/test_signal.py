import asyncio

import pytest

from app.signal_service import _parse_envelope, complete_signal_link


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_parse_envelope_extracts_text_message():
    entry = {
        "envelope": {
            "sourceNumber": "+491701234567",
            "sourceName": "Christoph",
            "timestamp": 1700000000000,
            "dataMessage": {"message": "Hallo!", "timestamp": 1700000000000},
        }
    }
    parsed = _parse_envelope(entry)
    assert parsed is not None
    assert parsed["from_number"] == "+491701234567"
    assert parsed["from_name"] == "Christoph"
    assert parsed["text"] == "Hallo!"
    assert parsed["received_at"] is not None


def test_parse_envelope_skips_receipts_without_data_message():
    entry = {"envelope": {"sourceNumber": "+491701234567", "receiptMessage": {"when": 123}}}
    assert _parse_envelope(entry) is None


def test_parse_envelope_handles_malformed_entry():
    assert _parse_envelope({}) is None
    assert _parse_envelope({"envelope": "not-a-dict"}) is None


def test_complete_signal_link_saves_newly_linked_number(monkeypatch, db_session):
    async def fake_list_linked_accounts():
        return ["+491701234567", "+491709999999"]

    monkeypatch.setattr("app.signal_service._list_linked_accounts", fake_list_linked_accounts)

    result = asyncio.run(
        complete_signal_link(
            db_session,
            user_id="user-1",
            accounts_before=["+491701234567"],
        )
    )
    assert result == {"connected": True, "account": "+491709999999"}

    from app.user_integration_store import user_integration_status

    status = user_integration_status(db_session, user_id="user-1", provider="signal")
    assert status["connected"] is True
    assert status["account"] == "+491709999999"


def test_complete_signal_link_not_yet_scanned(monkeypatch, db_session):
    async def fake_list_linked_accounts():
        return ["+491701234567"]

    monkeypatch.setattr("app.signal_service._list_linked_accounts", fake_list_linked_accounts)

    result = asyncio.run(
        complete_signal_link(db_session, user_id="user-1", accounts_before=["+491701234567"])
    )
    assert result == {"connected": False}


def test_signal_status_route_reports_service_not_configured(auth_client):
    response = auth_client.get("/api/integrations/signal/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is False
    assert payload["service_configured"] is False


def test_signal_send_requires_connection(auth_client):
    response = auth_client.post(
        "/api/integrations/signal/send",
        json={"to": "+491701234567", "message": "Hi"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "signal_not_configured"
