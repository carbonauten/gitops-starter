from io import BytesIO

from app.office_embed_service import is_office_filename, mint_preview_token, office_viewer_embed_url, parse_preview_token


def test_is_office_filename():
    assert is_office_filename("Plan.docx")
    assert is_office_filename("sheet.XLSX")
    assert not is_office_filename("notes.txt")


def test_office_viewer_embed_url_encodes_src():
    url = office_viewer_embed_url("https://example.com/a b.docx")
    assert url.startswith("https://view.officeapps.live.com/op/embed.aspx?src=")
    assert "a%20b.docx" in url


def test_preview_token_roundtrip():
    token = mint_preview_token("file-123", user_id="user-1")
    payload = parse_preview_token(token)
    assert payload["file_id"] == "file-123"
    assert payload["user_id"] == "user-1"


def test_onedrive_office_session_mock(auth_client):
    response = auth_client.get(
        "/api/files/office/session",
        params={"source": "onedrive", "item_id": "od-file-1"},
    )
    assert response.status_code == 200
    session = response.json()["session"]
    assert session["source"] == "onedrive"
    assert session["can_edit"] is True
    assert session["edit_url"]
    assert session["mock"] is True


def test_platform_office_session_and_public_preview(auth_client):
    upload = auth_client.post(
        "/api/files/upload",
        files={
            "upload": (
                "briefing.docx",
                BytesIO(b"PK\x03\x04fake-docx"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"folder": "general"},
    )
    assert upload.status_code == 201
    file_id = upload.json()["file"]["id"]

    session_resp = auth_client.get(
        "/api/files/office/session",
        params={"source": "platform", "item_id": file_id},
    )
    assert session_resp.status_code == 200
    session = session_resp.json()["session"]
    assert session["can_edit"] is False
    assert "view.officeapps.live.com" in session["embed_url"]
    assert "public-preview" in session["preview_url"]

    from urllib.parse import parse_qs, urlparse

    token = parse_qs(urlparse(session["preview_url"]).query)["token"][0]
    preview = auth_client.get("/api/files/public-preview", params={"token": token})
    assert preview.status_code == 200
    assert preview.content.startswith(b"PK")


def test_platform_office_session_rejects_non_office(auth_client):
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    file_id = upload.json()["file"]["id"]
    response = auth_client.get(
        "/api/files/office/session",
        params={"source": "platform", "item_id": file_id},
    )
    assert response.status_code == 400
