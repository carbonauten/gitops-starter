from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import patch


def _build_raw_message() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "Hallo Welt"
    msg["From"] = "Sender <sender@test.de>"
    msg["To"] = "empfaenger@test.de"
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    msg.set_content("Hallo, das ist der Text.")
    return msg.as_bytes()


class FakeImapConnection:
    """Standalone fake, not a real imaplib.IMAP4 - patching imaplib.IMAP4_SSL
    directly would require a real TCP handshake. We patch the module's own
    _connect() helper instead, same approach as the Mailcow httpx fake."""

    def __init__(self, uids: list[bytes], header_raw: bytes, full_raw: bytes):
        self.uids = uids
        self.header_raw = header_raw
        self.full_raw = full_raw
        self.search_calls: list[tuple] = []

    def select(self, folder, readonly=True):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "search":
            self.search_calls.append(args)
            return "OK", [b" ".join(self.uids)]
        if command == "fetch":
            uid, spec = args[0], args[1]
            if "HEADER.FIELDS" in spec:
                meta = f"{uid.decode()} (FLAGS (\\Seen) BODY[HEADER.FIELDS (SUBJECT FROM DATE)] {{{len(self.header_raw)}}}".encode()
                return "OK", [(meta, self.header_raw), b")"]
            meta = f"{uid.decode()} (FLAGS (\\Seen) BODY[] {{{len(self.full_raw)}}}".encode()
            return "OK", [(meta, self.full_raw), b")"]
        raise AssertionError(f"unexpected uid command: {command}")

    def close(self):
        pass

    def logout(self):
        pass


def _create_account(it_auth_client) -> dict:
    # Creating an account now tests the connection before saving, so even a
    # "just create it" call needs a working fake IMAP connection patched in.
    with patch("app.imap_mail_service._connect", return_value=FakeImapConnection(uids=[], header_raw=b"", full_raw=b"")):
        response = it_auth_client.post(
            "/api/imap-mail/accounts",
            json={
                "label": "Info (Strato)",
                "host": "imap.strato.de",
                "port": 993,
                "use_ssl": True,
                "username": "info@carbonauten.com",
                "password": "super-secret",
                "folder": "INBOX",
            },
        )
    assert response.status_code == 201
    return response.json()["account"]


def test_editor_cannot_manage_imap_accounts(auth_client):
    response = auth_client.get("/api/imap-mail/accounts")
    assert response.status_code == 403


def test_it_master_creates_lists_and_deletes_account(it_auth_client):
    account = _create_account(it_auth_client)
    assert account["label"] == "Info (Strato)"
    assert account["host"] == "imap.strato.de"
    assert "password" not in account

    listing = it_auth_client.get("/api/imap-mail/accounts")
    assert listing.status_code == 200
    assert any(entry["id"] == account["id"] for entry in listing.json()["accounts"])

    deleted = it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")
    assert deleted.status_code == 204

    listing_after = it_auth_client.get("/api/imap-mail/accounts")
    assert not any(entry["id"] == account["id"] for entry in listing_after.json()["accounts"])


def test_create_account_rejects_missing_password(it_auth_client):
    response = it_auth_client.post(
        "/api/imap-mail/accounts",
        json={
            "label": "Broken",
            "host": "imap.strato.de",
            "username": "broken@carbonauten.com",
            "password": "",
        },
    )
    assert response.status_code in (400, 422)


def test_list_and_get_messages_via_fake_imap(it_auth_client):
    account = _create_account(it_auth_client)
    header_raw = (
        b"Subject: Hallo Welt\r\n"
        b"From: Sender <sender@test.de>\r\n"
        b"Date: Mon, 01 Jan 2024 10:00:00 +0000\r\n\r\n"
    )
    full_raw = _build_raw_message()
    fake_conn = FakeImapConnection(uids=[b"1"], header_raw=header_raw, full_raw=full_raw)

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        listing = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages")
        assert listing.status_code == 200
        messages = listing.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["subject"] == "Hallo Welt"
        assert messages[0]["from"]["email"] == "sender@test.de"
        assert messages[0]["is_read"] is True

        detail = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages/1")
        assert detail.status_code == 200
        message = detail.json()["message"]
        assert message["subject"] == "Hallo Welt"
        assert message["body_type"] == "text"
        assert "Hallo, das ist der Text." in message["body"]

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_summarize_requires_ai_configured(it_auth_client):
    account = _create_account(it_auth_client)
    response = it_auth_client.post(
        f"/api/imap-mail/accounts/{account['id']}/messages/1/summarize",
        json={"language": "de"},
    )
    assert response.status_code == 503
    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_create_account_rejects_bad_credentials_without_saving(it_auth_client):
    from fastapi import HTTPException

    with patch(
        "app.imap_mail_service._connect",
        side_effect=HTTPException(status_code=502, detail="imap_login_failed"),
    ):
        response = it_auth_client.post(
            "/api/imap-mail/accounts",
            json={
                "label": "Wrong password",
                "host": "imap.strato.de",
                "port": 993,
                "use_ssl": True,
                "username": "info@carbonauten.com",
                "password": "wrong-password",
                "folder": "INBOX",
            },
        )
    assert response.status_code == 502

    listing = it_auth_client.get("/api/imap-mail/accounts")
    assert not any(entry["label"] == "Wrong password" for entry in listing.json()["accounts"])


def test_list_messages_forwards_search_term_to_imap(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], header_raw=b"Subject: X\r\n\r\n", full_raw=b"")

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        response = it_auth_client.get(
            f"/api/imap-mail/accounts/{account['id']}/messages",
            params={"q": "Rechnung"},
        )
    assert response.status_code == 200
    assert fake_conn.search_calls, "expected at least one uid('search', ...) call"
    criteria = fake_conn.search_calls[-1]
    assert "SUBJECT" in criteria
    assert '"Rechnung"' in criteria
    assert "FROM" in criteria

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")
