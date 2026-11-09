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
    _connect() helper instead, same approach as the Mailcow httpx fake.

    Both the list and detail fetches now request BODY.PEEK[] (optionally
    byte-ranged) plus BODYSTRUCTURE, so a single full_raw response serves
    both - include_bodystructure lets a test simulate a message with an
    attachment, since real servers put the word ATTACHMENT inline in the
    same response line imaplib.ParseFlags already scans for flags."""

    def __init__(self, uids: list[bytes], full_raw: bytes, has_attachment: bool = False):
        self.uids = uids
        self.full_raw = full_raw
        self.has_attachment = has_attachment
        self.search_calls: list[tuple] = []

    def select(self, folder, readonly=True):
        return "OK", [b"1"]

    def uid(self, command, *args):
        if command == "search":
            self.search_calls.append(args)
            return "OK", [b" ".join(self.uids)]
        if command == "fetch":
            uid = args[0]
            bodystructure = (
                '(("APPLICATION" "PDF" ("NAME" "invoice.pdf") NIL NIL "BASE64" 4096 NIL '
                '("ATTACHMENT" ("FILENAME" "invoice.pdf")) NIL))'
                if self.has_attachment
                else '("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 123 5)'
            )
            meta = (
                f"{uid.decode()} (FLAGS (\\Seen) BODYSTRUCTURE {bodystructure} "
                f"BODY[] {{{len(self.full_raw)}}}"
            ).encode()
            return "OK", [(meta, self.full_raw), b")"]
        raise AssertionError(f"unexpected uid command: {command}")

    def close(self):
        pass

    def logout(self):
        pass


def _create_account(it_auth_client) -> dict:
    # Creating an account now tests the connection before saving, so even a
    # "just create it" call needs a working fake IMAP connection patched in.
    with patch("app.imap_mail_service._connect", return_value=FakeImapConnection(uids=[], full_raw=b"")):
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
    full_raw = _build_raw_message()
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=full_raw)

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        listing = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages")
        assert listing.status_code == 200
        messages = listing.json()["messages"]
        assert len(messages) == 1
        assert messages[0]["subject"] == "Hallo Welt"
        assert messages[0]["from"]["email"] == "sender@test.de"
        assert messages[0]["is_read"] is True
        assert messages[0]["preview"] == "Hallo, das ist der Text."
        assert messages[0]["has_attachments"] is False

        detail = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages/1")
        assert detail.status_code == 200
        message = detail.json()["message"]
        assert message["subject"] == "Hallo Welt"
        assert message["body_type"] == "text"
        assert "Hallo, das ist der Text." in message["body"]
        assert message["preview"] == "Hallo, das ist der Text."
        assert message["has_attachments"] is False

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_list_messages_detects_attachment_from_bodystructure(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message(), has_attachment=True)

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        listing = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages")
    assert listing.status_code == 200
    assert listing.json()["messages"][0]["has_attachments"] is True

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
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=b"")

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


def test_update_account_changes_fields_and_tests_connection(it_auth_client):
    account = _create_account(it_auth_client)

    with patch(
        "app.imap_mail_service._connect", return_value=FakeImapConnection(uids=[], full_raw=b"")
    ) as mock_connect:
        response = it_auth_client.put(
            f"/api/imap-mail/accounts/{account['id']}",
            json={
                "label": "Info (Strato) renamed",
                "host": "imap.strato.de",
                "port": 993,
                "use_ssl": True,
                "username": "info@carbonauten.com",
                "password": "",
                "folder": "Archive",
            },
        )
    assert response.status_code == 200
    updated = response.json()["account"]
    assert updated["label"] == "Info (Strato) renamed"
    assert updated["folder"] == "Archive"
    assert mock_connect.called  # the blank password still triggers a fail-fast test

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_update_account_rejects_bad_new_password_without_saving(it_auth_client):
    account = _create_account(it_auth_client)
    from fastapi import HTTPException

    with patch(
        "app.imap_mail_service._connect",
        side_effect=HTTPException(status_code=502, detail="imap_login_failed"),
    ):
        response = it_auth_client.put(
            f"/api/imap-mail/accounts/{account['id']}",
            json={
                "label": "Info (Strato)",
                "host": "imap.strato.de",
                "port": 993,
                "use_ssl": True,
                "username": "info@carbonauten.com",
                "password": "a-new-wrong-password",
                "folder": "INBOX",
            },
        )
    assert response.status_code == 502

    unchanged = it_auth_client.get("/api/imap-mail/accounts").json()["accounts"]
    assert any(entry["label"] == "Info (Strato)" for entry in unchanged)

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")
