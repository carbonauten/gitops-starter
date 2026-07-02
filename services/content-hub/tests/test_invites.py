from datetime import datetime, timedelta, timezone

from tests.conftest import TEST_EMAIL


def test_it_master_can_create_and_accept_invite(it_auth_client, client):
    invite_email = "new.colleague@example.com"
    response = it_auth_client.post(
        "/api/user/invites",
        json={"email": invite_email, "role": "viewer"},
    )
    assert response.status_code == 200
    invite = response.json()["invite"]
    assert invite["email"] == invite_email
    assert invite["role"] == "viewer"
    assert invite["status"] == "pending"
    assert "/invite/" in invite["invite_url"]

    token = invite["invite_url"].rsplit("/invite/", 1)[-1]
    preview = client.get(f"/api/auth/invite/{token}")
    assert preview.status_code == 200
    assert preview.json()["invite"]["email"] == invite_email

    accept = client.post(
        "/api/auth/accept-invite",
        json={"token": token, "name": "New Colleague", "password": "welcome-pass-1"},
    )
    assert accept.status_code == 200
    user = accept.json()["user"]
    assert user["email"] == invite_email
    assert user["role"] == "viewer"
    assert user["name"] == "New Colleague"

    login = client.post(
        "/api/auth/login",
        json={"email": invite_email, "password": "welcome-pass-1"},
    )
    assert login.status_code == 200


def test_cannot_invite_existing_active_user(it_auth_client):
    response = it_auth_client.post(
        "/api/user/invites",
        json={"email": TEST_EMAIL, "role": "editor"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "user_exists"


def test_editor_cannot_manage_invites(auth_client):
    response = auth_client.post(
        "/api/user/invites",
        json={"email": "blocked@example.com", "role": "viewer"},
    )
    assert response.status_code == 403


def test_expired_invite_cannot_be_accepted(it_auth_client, client):
    from app.database import UserInvite, _SessionLocal

    invite_email = "expired@example.com"
    created = it_auth_client.post(
        "/api/user/invites",
        json={"email": invite_email, "role": "editor"},
    )
    token = created.json()["invite"]["invite_url"].rsplit("/invite/", 1)[-1]

    db = _SessionLocal()
    try:
        invite = db.get(UserInvite, created.json()["invite"]["id"])
        invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/auth/accept-invite",
        json={"token": token, "name": "Too Late", "password": "welcome-pass-1"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invite_expired"


def test_revoke_invite(it_auth_client):
    created = it_auth_client.post(
        "/api/user/invites",
        json={"email": "revoked@example.com", "role": "editor"},
    )
    invite_id = created.json()["invite"]["id"]
    deleted = it_auth_client.delete(f"/api/user/invites/{invite_id}")
    assert deleted.status_code == 204

    listing = it_auth_client.get("/api/user/invites")
    assert all(invite["id"] != invite_id or invite["status"] != "pending" for invite in listing.json()["invites"])
