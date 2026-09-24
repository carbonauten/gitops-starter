from app.graph_directory_service import reset_mock_directory
from app.m365_ai_service import looks_like_m365_admin_question, parse_directory_intent
from unittest.mock import patch
import asyncio
import json


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
    assert parse_directory_intent("Welche M365 Lizenzen sind frei?")["action"] == "list_licenses"
    assign = parse_directory_intent("Weise anna@carbonauten.com Business Premium Lizenz zu")
    assert assign["action"] == "assign_license"
    assert assign["email"] == "anna@carbonauten.com"
    assert "premium" in assign["sku"].lower()
    assert looks_like_m365_admin_question("Weise Mike eine Business Premium Lizenz zu")
    assert not looks_like_m365_admin_question("biochar kiln status")
    assert not looks_like_m365_admin_question("What licenses does our product have?")
    assert not looks_like_m365_admin_question("remove john@example.com from mailing list")


def test_handle_directory_question_uses_function_calling(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def fake_chat(messages, **kwargs):
        assert kwargs.get("tools")
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "name": "list_m365_users",
                    "arguments": '{"query":"mike"}',
                }
            ],
        }

    with patch("app.m365_ai_service.chat_completion_raw", side_effect=fake_chat):
        from app.m365_ai_service import handle_directory_question

        result = asyncio.run(handle_directory_question("Zeig mir bitte Mike im M365 Verzeichnis", language="de"))

    assert result["mode"] == "function_calling"
    assert result["action"] == "list"
    assert any("mike.mueller@carbonauten.com" in (u.get("user_principal_name") or "") for u in result["users"])
    get_settings.cache_clear()


def test_function_calling_can_assign_license_by_name(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def fake_chat(messages, **kwargs):
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_2",
                    "name": "assign_m365_license",
                    "arguments": json.dumps(
                        {
                            "user": "chibi.guest@carbonauten.com",
                            "sku": "Business Premium",
                        }
                    ),
                }
            ],
        }

    with patch("app.m365_ai_service.chat_completion_raw", side_effect=fake_chat):
        from app.m365_ai_service import handle_directory_question

        result = asyncio.run(
            handle_directory_question(
                "Bitte weise chibi.guest@carbonauten.com Business Premium zu",
                language="de",
            )
        )

    assert result["mode"] == "function_calling"
    assert result["action"] == "assign_license"
    assert "Microsoft 365 Business Premium" in (result["user"] or {}).get("licenses", [])
    get_settings.cache_clear()


def test_m365_ask_reports_regex_mode_without_ai(it_auth_client):
    listed = it_auth_client.post(
        "/api/m365/ask",
        json={"question": "Welche M365 Benutzer gibt es?", "language": "de"},
    )
    assert listed.status_code == 200
    assert listed.json()["mode"] == "regex"


def test_regex_assign_license_extracts_sku(it_auth_client):
    response = it_auth_client.post(
        "/api/m365/ask",
        json={
            "question": "Weise chibi.guest@carbonauten.com Business Premium Lizenz zu",
            "language": "de",
        },
    )
    assert response.status_code == 200
    assert response.json()["action"] == "assign_license"
    assert response.json()["mode"] == "regex"
    licenses = (response.json().get("user") or {}).get("licenses", [])
    assert any("Business Premium" in name for name in licenses)
    assert "zugewiesen" in response.json()["answer"].lower() or "assigned" in response.json()["answer"].lower()


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
