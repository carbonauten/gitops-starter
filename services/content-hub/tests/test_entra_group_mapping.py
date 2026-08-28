from tests.conftest import TEST_EMAIL


def test_editor_cannot_manage_group_mappings(auth_client):
    assert auth_client.get("/api/user/group-mappings").status_code == 403
    response = auth_client.post(
        "/api/user/group-mappings",
        json={"entra_group_id": "grp-1", "entra_group_name": "Redaktion", "role": "editor"},
    )
    assert response.status_code == 403


def test_it_master_can_create_list_and_delete_group_mapping(it_auth_client):
    created = it_auth_client.post(
        "/api/user/group-mappings",
        json={"entra_group_id": "grp-editors", "entra_group_name": "Redaktion", "role": "editor"},
    )
    assert created.status_code == 200
    mapping = created.json()["mapping"]
    assert mapping["entra_group_id"] == "grp-editors"
    assert mapping["role"] == "editor"

    listing = it_auth_client.get("/api/user/group-mappings")
    assert listing.status_code == 200
    assert any(row["id"] == mapping["id"] for row in listing.json()["mappings"])

    deleted = it_auth_client.delete(f"/api/user/group-mappings/{mapping['id']}")
    assert deleted.status_code == 204

    listing_after = it_auth_client.get("/api/user/group-mappings")
    assert all(row["id"] != mapping["id"] for row in listing_after.json()["mappings"])


def test_duplicate_group_mapping_rejected(it_auth_client):
    payload = {"entra_group_id": "grp-dup", "entra_group_name": "Dup", "role": "viewer"}
    first = it_auth_client.post("/api/user/group-mappings", json=payload)
    assert first.status_code == 200
    second = it_auth_client.post("/api/user/group-mappings", json=payload)
    assert second.status_code == 409


def test_invalid_role_rejected(it_auth_client):
    response = it_auth_client.post(
        "/api/user/group-mappings",
        json={"entra_group_id": "grp-bad", "entra_group_name": "Bad", "role": "superadmin"},
    )
    assert response.status_code == 422


def test_resolve_role_from_groups_priority(client):
    from app.database import _SessionLocal
    from app.entra_group_service import create_group_mapping, resolve_role_from_groups

    db = _SessionLocal()
    try:
        create_group_mapping(db, entra_group_id="grp-editor", entra_group_name="Editors", role="editor")
        create_group_mapping(db, entra_group_id="grp-itmaster", entra_group_name="IT", role="it_master")

        # Member of both groups -> higher-priority role (it_master) wins
        assert resolve_role_from_groups(db, ["grp-editor", "grp-itmaster"]) == "it_master"
        assert resolve_role_from_groups(db, ["grp-editor"]) == "editor"
        # No matching mapping -> None so callers don't clobber the existing role
        assert resolve_role_from_groups(db, ["grp-unmapped"]) is None
        assert resolve_role_from_groups(db, []) is None
    finally:
        db.close()


def test_login_applies_group_role_and_locks_after_manual_override(client):
    from app.database import _SessionLocal
    from app.entra_group_service import create_group_mapping
    from app.user_service import ROLE_SOURCE_ENTRA_GROUP, ROLE_SOURCE_MANUAL, update_user_role, upsert_user_from_login

    db = _SessionLocal()
    try:
        create_group_mapping(db, entra_group_id="grp-certs", entra_group_name="Zertifikate", role="certificate_manager")

        user = upsert_user_from_login(
            db,
            entra_id="entra-groups-1",
            email="groups-user@carbonauten.com",
            name="Groups User",
            group_ids=["grp-certs"],
        )
        assert user.role == "certificate_manager"
        assert user.role_source == ROLE_SOURCE_ENTRA_GROUP

        # Next login without that group anymore -> no mapping match, role stays (no None-role fallback)
        user = upsert_user_from_login(
            db,
            entra_id="entra-groups-1",
            email="groups-user@carbonauten.com",
            name="Groups User",
            group_ids=["grp-unrelated"],
        )
        assert user.role == "certificate_manager"

        # IT master manually overrides the role -> locks out future group sync
        update_user_role(db, user.id, "viewer")
        db.refresh(user)
        assert user.role_source == ROLE_SOURCE_MANUAL

        user = upsert_user_from_login(
            db,
            entra_id="entra-groups-1",
            email="groups-user@carbonauten.com",
            name="Groups User",
            group_ids=["grp-certs"],
        )
        assert user.role == "viewer"
    finally:
        db.close()
