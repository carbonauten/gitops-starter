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


def _build_raw_message_with_attachment() -> bytes:
    msg = EmailMessage()
    msg["Subject"] = "Mit Anhang"
    msg["From"] = "Sender <sender@test.de>"
    msg["To"] = "empfaenger@test.de"
    msg["Date"] = "Mon, 01 Jan 2024 10:00:00 +0000"
    msg.set_content("Siehe Anhang.")
    msg.add_attachment(b"%PDF-1.4 fake pdf bytes", maintype="application", subtype="pdf", filename="invoice.pdf")
    return msg.as_bytes()


class FakeImapConnection:
    """Standalone fake, not a real imaplib.IMAP4 - patching imaplib.IMAP4_SSL
    directly would require a real TCP handshake. We patch the module's own
    _connect() helper instead, same approach as the Mailcow httpx fake.

    Both the list and detail fetches now request BODY.PEEK[] (optionally
    byte-ranged) plus BODYSTRUCTURE, so a single full_raw response serves
    both - include_bodystructure lets a test simulate a message with an
    attachment, since real servers put the word ATTACHMENT inline in the
    same response line imaplib.ParseFlags already scans for flags. Actual
    attachment detection/download (get_message/get_attachment) now goes
    through email.message.EmailMessage.iter_attachments() on the real
    parsed message instead, so full_raw itself needs a genuine multipart
    message for those tests - see _build_raw_message_with_attachment()."""

    def __init__(self, uids: list[bytes], full_raw: bytes, has_attachment: bool = False):
        self.uids = uids
        self.full_raw = full_raw
        self.has_attachment = has_attachment
        self.search_calls: list[tuple] = []
        self.select_calls: list[str] = []

    def select(self, folder, readonly=True):
        self.select_calls.append(folder)
        return "OK", [b"1"]

    def list(self, directory='""', pattern="*"):
        return "OK", [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Sent"',
            b'(\\Noselect \\HasChildren) "/" "[Gmail]"',
        ]

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


def test_decode_imap_utf7_handles_non_ascii_folder_names():
    from app.imap_mail_service import _decode_imap_utf7

    # Verified against a from-scratch modified-UTF-7 encoder (RFC 3501),
    # not just plausible-looking - "Ä" (U+00C4) base64-encodes to "AMQ".
    assert _decode_imap_utf7("Rechnungen/&AMQ--Ordner") == "Rechnungen/Ä-Ordner"
    assert _decode_imap_utf7("INBOX") == "INBOX"
    assert _decode_imap_utf7("Sent") == "Sent"


def test_parse_list_response_marks_noselect_folders():
    from app.imap_mail_service import _parse_list_response

    assert _parse_list_response(b'(\\HasNoChildren) "/" "INBOX"') == {"name": "INBOX", "selectable": True}
    assert _parse_list_response(b'(\\Noselect \\HasChildren) "/" "[Gmail]"') == {
        "name": "[Gmail]",
        "selectable": False,
    }
    assert _parse_list_response(b"not a list response") is None


def test_list_folders(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[], full_raw=b"")

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        response = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/folders")
    assert response.status_code == 200
    folders = response.json()["folders"]
    names = {f["name"]: f["selectable"] for f in folders}
    assert names == {"INBOX": True, "Sent": True, "[Gmail]": False}

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_list_messages_uses_requested_folder(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message())

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        response = it_auth_client.get(
            f"/api/imap-mail/accounts/{account['id']}/messages", params={"folder": "Sent"}
        )
    assert response.status_code == 200
    assert fake_conn.select_calls[-1] == "Sent"

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_get_message_includes_real_attachments(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message_with_attachment())

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        detail = it_auth_client.get(f"/api/imap-mail/accounts/{account['id']}/messages/1")
    assert detail.status_code == 200
    message = detail.json()["message"]
    assert message["has_attachments"] is True
    assert len(message["attachments"]) == 1
    assert message["attachments"][0]["filename"] == "invoice.pdf"
    assert message["attachments"][0]["content_type"] == "application/pdf"

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_download_attachment_returns_file_content(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message_with_attachment())

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        response = it_auth_client.get(
            f"/api/imap-mail/accounts/{account['id']}/messages/1/attachments/0"
        )
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake pdf bytes"
    assert response.headers["content-type"] == "application/pdf"
    assert "invoice.pdf" in response.headers["content-disposition"]

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_download_attachment_invalid_index_404(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message_with_attachment())

    with patch("app.imap_mail_service._connect", return_value=fake_conn):
        response = it_auth_client.get(
            f"/api/imap-mail/accounts/{account['id']}/messages/1/attachments/5"
        )
    assert response.status_code == 404

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_summarize_requires_ai_configured(it_auth_client):
    account = _create_account(it_auth_client)
    response = it_auth_client.post(
        f"/api/imap-mail/accounts/{account['id']}/messages/1/summarize",
        json={"language": "de"},
    )
    assert response.status_code == 503
    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_draft_reply_requires_ai_configured(it_auth_client):
    account = _create_account(it_auth_client)
    response = it_auth_client.post(
        f"/api/imap-mail/accounts/{account['id']}/messages/1/draft-reply",
        json={"instructions": "", "language": "de"},
    )
    assert response.status_code == 503
    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_translate_message_requires_ai_configured(it_auth_client):
    account = _create_account(it_auth_client)
    response = it_auth_client.post(
        f"/api/imap-mail/accounts/{account['id']}/messages/1/translate",
        json={"target_language": "en"},
    )
    assert response.status_code == 503
    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_draft_reply_success(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message())

    with (
        patch("app.routes.imap_mail.ai_configured", return_value=True),
        patch("app.routes.imap_mail.draft_email_reply", return_value="Vielen Dank fuer Ihre Nachricht."),
        patch("app.imap_mail_service._connect", return_value=fake_conn),
    ):
        response = it_auth_client.post(
            f"/api/imap-mail/accounts/{account['id']}/messages/1/draft-reply",
            json={"instructions": "kurz und freundlich", "language": "de"},
        )
    assert response.status_code == 200
    assert response.json()["reply"] == "Vielen Dank fuer Ihre Nachricht."

    it_auth_client.delete(f"/api/imap-mail/accounts/{account['id']}")


def test_translate_message_success(it_auth_client):
    account = _create_account(it_auth_client)
    fake_conn = FakeImapConnection(uids=[b"1"], full_raw=_build_raw_message())

    with (
        patch("app.routes.imap_mail.ai_configured", return_value=True),
        patch("app.routes.imap_mail.translate_email_body", return_value="Thank you for your message."),
        patch("app.imap_mail_service._connect", return_value=fake_conn),
    ):
        response = it_auth_client.post(
            f"/api/imap-mail/accounts/{account['id']}/messages/1/translate",
            json={"target_language": "en"},
        )
    assert response.status_code == 200
    translation = response.json()["translation"]
    assert translation["body"] == "Thank you for your message."
    assert translation["body_type"] == "text"

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
