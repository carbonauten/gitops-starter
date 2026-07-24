from datetime import date, timedelta


def test_dashboard_home_personal(auth_client):
    created = auth_client.post(
        "/api/articles",
        json={"title": "My Draft Piece", "content": "<p>hello</p>"},
    )
    assert created.status_code == 201

    home = auth_client.get("/api/dashboard/home")
    assert home.status_code == 200
    payload = home.json()["home"]
    assert payload["counts"]["my_drafts"] >= 1
    assert any(item["title"] == "My Draft Piece" for item in payload["my_drafts"])


def test_dashboard_calendar_includes_scheduled_and_expiry(auth_client):
    # create certificate expiring soon
    auth_client.post(
        "/api/certificates",
        json={
            "name": "Calendar Cert",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": (date.today() - timedelta(days=10)).isoformat(),
            "valid_to": (date.today() + timedelta(days=20)).isoformat(),
            "responsible_name": "Quality",
            "responsible_email": "demo@example.com",
        },
    )

    calendar = auth_client.get("/api/dashboard/calendar")
    assert calendar.status_code == 200
    body = calendar.json()
    payload = body["calendar"]
    assert "events" in payload
    assert "by_date" in payload
    assert "outlook" in body
    assert body["outlook"]["connected"] is False
    assert any(event["type"] == "certificate_expiry" and event["title"] == "Calendar Cert" for event in payload["events"])
