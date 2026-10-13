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


def test_upload_master_requires_it_master(auth_client):
    """Editors (and other non-IT-Master roles) cannot use the master-documents upload."""
    payload = BytesIO(b"should be rejected")
    response = auth_client.post(
        "/api/files/upload-master",
        files={"uploads": ("blocked.txt", payload, "text/plain")},
    )
    assert response.status_code == 403


def test_upload_master_multiple_files_in_one_request(it_auth_client):
    upload = it_auth_client.post(
        "/api/files/upload-master",
        files=[
            ("uploads", ("a.txt", BytesIO(b"file a"), "text/plain")),
            ("uploads", ("b.txt", BytesIO(b"file b"), "text/plain")),
        ],
    )
    assert upload.status_code == 201
    files = upload.json()["files"]
    assert len(files) == 2
    assert {f["original_name"] for f in files} == {"a.txt", "b.txt"}

    for file_entry in files:
        download = it_auth_client.get(f"/api/files/{file_entry['id']}/download")
        assert download.status_code == 200
        assert download.content in (b"file a", b"file b")


def test_upload_master_stores_content_in_postgres(it_auth_client):
    from app.database import FileAsset, _SessionLocal

    payload = BytesIO(b"stored directly in postgres")
    upload = it_auth_client.post(
        "/api/files/upload-master",
        files={"uploads": ("db-stored.bin", payload, "application/octet-stream")},
    )
    file_id = upload.json()["files"][0]["id"]

    db = _SessionLocal()
    try:
        file_asset = db.get(FileAsset, file_id)
        assert file_asset.storage_path == "db://postgres"
        assert file_asset.content == b"stored directly in postgres"
    finally:
        db.close()

    # listing/download/delete are the same shared endpoints used for local/OSS
    # files - confirm they transparently handle Postgres-stored content too.
    download = it_auth_client.get(f"/api/files/{file_id}/download")
    assert download.status_code == 200
    assert download.content == b"stored directly in postgres"

    delete = it_auth_client.delete(f"/api/files/{file_id}")
    assert delete.status_code == 204
