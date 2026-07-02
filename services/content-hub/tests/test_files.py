from io import BytesIO


def test_upload_list_and_download_file(auth_client):
    payload = BytesIO(b"sample file content")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("report.pdf", payload, "application/pdf")},
        data={"folder": "compliance"},
    )
    assert upload.status_code == 201
    file_id = upload.json()["file"]["id"]

    listing = auth_client.get("/api/files", params={"folder": "compliance"})
    assert listing.status_code == 200
    assert len(listing.json()["files"]) == 1
    assert "compliance" in listing.json()["folders"]

    download = auth_client.get(f"/api/files/{file_id}/download")
    assert download.status_code == 200
    assert download.content == b"sample file content"

    search = auth_client.get("/api/search", params={"q": "report"})
    assert search.status_code == 200
    assert any(item["type"] == "file" for item in search.json()["results"])


def test_delete_file(auth_client):
    payload = BytesIO(b"delete me")
    upload = auth_client.post(
        "/api/files/upload",
        files={"upload": ("delete.txt", payload, "text/plain")},
    )
    file_id = upload.json()["file"]["id"]
    delete = auth_client.delete(f"/api/files/{file_id}")
    assert delete.status_code == 204
