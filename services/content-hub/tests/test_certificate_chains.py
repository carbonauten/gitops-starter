from datetime import date, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch


def _future(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _past(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _create(auth_client, name: str, days_left: int = 200, parent_id=None, escalate_email=""):
    payload = {
        "name": name,
        "category": "compliance",
        "issuer": "TÜV",
        "valid_from": _past(30),
        "valid_to": _future(days_left),
        "responsible_name": "Quality",
        "responsible_email": "quality@example.com",
        "escalate_email": escalate_email,
        "notes": "",
    }
    if parent_id:
        payload["parent_id"] = parent_id
    response = auth_client.post("/api/certificates", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["certificate"]


def test_certificate_parent_child_chain(auth_client):
    parent = _create(auth_client, "ISO 9001 Root", days_left=400)
    child = _create(auth_client, "ISO 9001 Audit Report", days_left=120, parent_id=parent["id"])

    fetched = auth_client.get(f"/api/certificates/{parent['id']}")
    assert fetched.status_code == 200
    body = fetched.json()["certificate"]
    assert len(body["children"]) == 1
    assert body["children"][0]["id"] == child["id"]

    child_fetched = auth_client.get(f"/api/certificates/{child['id']}")
    assert child_fetched.json()["certificate"]["parent_id"] == parent["id"]
    assert child_fetched.json()["certificate"]["parent_name"] == "ISO 9001 Root"

    chains = auth_client.get("/api/certificates/chains")
    assert chains.status_code == 200
    assert any(node["name"] == "ISO 9001 Root" for node in chains.json()["chains"])


def test_certificate_cycle_rejected(auth_client):
    parent = _create(auth_client, "Parent Cert", days_left=300)
    child = _create(auth_client, "Child Cert", days_left=200, parent_id=parent["id"])

    cycle = auth_client.patch(
        f"/api/certificates/{parent['id']}",
        json={"parent_id": child["id"]},
    )
    assert cycle.status_code == 422


def test_delete_blocked_when_children_exist(auth_client):
    parent = _create(auth_client, "Parent Keep", days_left=300)
    _create(auth_client, "Child Keep", days_left=200, parent_id=parent["id"])
    deleted = auth_client.delete(f"/api/certificates/{parent['id']}")
    assert deleted.status_code == 409


def test_audit_export_zip(auth_client):
    _create(auth_client, "Audit Cert", days_left=40)
    response = auth_client.get("/api/certificates/audit-export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.content[:2] == b"PK"


def test_reminder_windows_once(it_auth_client):
    cert = _create(it_auth_client, "Soon Expiring", days_left=25, escalate_email="lead@example.com")

    with patch("app.certificate_service.send_plain_email", return_value=True), patch(
        "app.publish_service._run_deliveries",
        new_callable=AsyncMock,
    ):
        first = it_auth_client.post("/api/publish/certificate-reminders")
        assert first.status_code == 200
        payload = first.json()
        assert payload["reminders_sent"] >= 1
        assert any(item["certificate_id"] == cert["id"] for item in payload["items"])

        second = it_auth_client.post("/api/publish/certificate-reminders")
        assert second.status_code == 200
        assert all(item["certificate_id"] != cert["id"] for item in second.json()["items"])
