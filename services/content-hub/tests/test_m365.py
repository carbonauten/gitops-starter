from app.graph_directory_service import reset_mock_directory
from app.m365_ai_service import looks_like_m365_admin_question, parse_directory_intent


def setup_function() -> None:
    reset_mock_directory()


def teardown_function() -> None:
    reset_mock_directory()


def test_editor_cannot_list_m365_users(auth_client):
    response = auth_client.get("/api/m365/users")
    assert response.status_code == 403


def test_it_master_lists_mock_directory(it_auth_client):
    listing = it_auth_client.get("/api/m365/users")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["mock"] is True
    upns = {row["user_principal_name"] for row in payload["users"]}
    assert "mike.mueller@carbonauten.com" in upns
    assert "torsten.becker@carbonauten.com" in upns


def test_it_master_can_search_and_block_user(it_auth_client):
    listing = it_auth_client.get("/api/m365/users", params={"q": "chibi"})
    assert listing.status_code == 200
    guest = listing.json()["users"][0]
    assert guest["account_enabled"] is False

    enabled = it_auth_client.patch(
        f"/api/m365/users/{guest['id']}/enabled",
        json={"account_enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["user"]["account_enabled"] is True

    blocked = it_auth_client.patch(
        f"/api/m365/users/{guest['id']}/enabled",
        json={"account_enabled": False},
    )
    assert blocked.json()["user"]["account_enabled"] is False


def test_it_master_can_create_user_and_reset_password(it_auth_client):
    created = it_auth_client.post(
        "/api/m365/users",
        json={
            "display_name": "Anna Beispiel",
            "user_principal_name": "anna.beispiel@carbonauten.com",
            "job_title": "Redaktion",
            "department": "Kommunikation",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["user"]["user_principal_name"] == "anna.beispiel@carbonauten.com"
    assert body["temporary_password"]
    user_id = body["user"]["id"]

    reset = it_auth_client.post(f"/api/m365/users/{user_id}/reset-password", json={})
    assert reset.status_code == 200
    assert reset.json()["temporary_password"]


def test_m365_ask_lists_and_creates(it_auth_client):
    listed = it_auth_client.post(
        "/api/m365/ask",
        json={"question": "Welche M365 Benutzer gibt es?", "language": "de"},
    )
    assert listed.status_code == 200
    assert listed.json()["action"] == "list"
    assert "mike.mueller@carbonauten.com" in listed.json()["answer"]

    created = it_auth_client.post(
        "/api/m365/ask",
        json={"question": "Lege user kai@carbonauten.com an", "language": "de"},
    )
    assert created.status_code == 200
    assert created.json()["action"] == "create"
    assert "kai@carbonauten.com" in created.json()["answer"]
    assert created.json()["temporary_password"]


def test_search_ask_m365_for_it_master(it_auth_client):
    response = it_auth_client.post(
        "/api/search/ask",
        json={"question": "Sperre chibi.guest@carbonauten.com", "language": "de"},
    )
    assert response.status_code == 200
    assert response.json()["m365_action"] == "disable"
    assert "gesperrt" in response.json()["answer"].lower() or "chibi.guest" in response.json()["answer"]


def test_search_ask_m365_ignored_for_editor(auth_client):
    response = auth_client.post(
        "/api/search/ask",
        json={"question": "Welche M365 Benutzer gibt es?", "language": "de"},
    )
    assert response.status_code == 200
    assert "m365_action" not in response.json() or response.json().get("m365_action") in (None, "")


def test_parse_directory_intent_examples():
    assert looks_like_m365_admin_question("Welche M365 Benutzer gibt es?")
    assert parse_directory_intent("Welche M365 Benutzer gibt es?")["query"] == ""
    assert parse_directory_intent("Sperre chibi.guest@carbonauten.com")["action"] == "disable"
    created = parse_directory_intent("Lege user anna@carbonauten.com an")
    assert created["action"] == "create"
    assert created["email"] == "anna@carbonauten.com"
    assert not looks_like_m365_admin_question("biochar kiln status")


def test_duplicate_m365_user_conflict(it_auth_client):
    first = it_auth_client.post(
        "/api/m365/users",
        json={"display_name": "Anna", "user_principal_name": "anna.beispiel@carbonauten.com"},
    )
    assert first.status_code == 200
    duplicate = it_auth_client.post(
        "/api/m365/users",
        json={"display_name": "Anna", "user_principal_name": "anna.beispiel@carbonauten.com"},
    )
    assert duplicate.status_code == 409


def test_it_master_lists_mock_groups(it_auth_client):
    response = it_auth_client.get("/api/m365/groups")
    assert response.status_code == 200
    names = {row["display_name"] for row in response.json()["groups"]}
    assert "IT-Master" in names

    filtered = it_auth_client.get("/api/m365/groups", params={"q": "redaktion"})
    assert filtered.status_code == 200
    assert all("redaktion" in row["display_name"].lower() for row in filtered.json()["groups"])


def test_editor_cannot_list_groups(auth_client):
    assert auth_client.get("/api/m365/groups").status_code == 403


def test_it_master_lists_mock_licenses(it_auth_client):
    response = it_auth_client.get("/api/m365/licenses")
    assert response.status_code == 200
    licenses = response.json()["licenses"]
    names = {row["name"] for row in licenses}
    assert "Microsoft 365 Business Premium" in names
    premium = next(row for row in licenses if row["name"] == "Microsoft 365 Business Premium")
    assert premium["available"] == premium["total"] - premium["consumed"]


def test_it_master_can_assign_and_remove_license(it_auth_client):
    listing = it_auth_client.get("/api/m365/users", params={"q": "chibi"})
    guest = listing.json()["users"][0]
    assert guest["licenses"] == []

    licenses = it_auth_client.get("/api/m365/licenses").json()["licenses"]
    sku_id = next(row["sku_id"] for row in licenses if row["name"] == "Microsoft 365 Business Standard")

    assigned = it_auth_client.post(f"/api/m365/users/{guest['id']}/licenses", json={"sku_id": sku_id})
    assert assigned.status_code == 200
    updated_user = assigned.json()["user"]
    assert "Microsoft 365 Business Standard" in updated_user["licenses"]
    assert any(entry["sku_id"] == sku_id for entry in updated_user["license_skus"])

    removed = it_auth_client.delete(f"/api/m365/users/{guest['id']}/licenses/{sku_id}")
    assert removed.status_code == 200
    assert "Microsoft 365 Business Standard" not in removed.json()["user"]["licenses"]


def test_editor_cannot_assign_license(auth_client):
    response = auth_client.post(
        "/api/m365/users/m365-guest-chibi/licenses",
        json={"sku_id": "mock-biz-standard"},
    )
    assert response.status_code == 403
