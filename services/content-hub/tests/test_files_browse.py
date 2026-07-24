def test_file_folder_tree(auth_client):
    response = auth_client.get("/api/files/folders/tree")
    assert response.status_code == 200
    folders = response.json()["folders"]
    assert len(folders) >= 3
    assert any(folder["slug"] == "general" for folder in folders)


def test_browse_platform(auth_client):
    response = auth_client.get("/api/files/browse", params={"source": "platform"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "platform"
    assert "folders" in payload
    assert "files" in payload


def test_browse_sharepoint_mock(auth_client):
    response = auth_client.get("/api/files/browse", params={"source": "sharepoint"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "sharepoint"
    assert payload["mock"] is True
    assert len(payload["folders"]) >= 1


def test_browse_onedrive_mock(auth_client):
    response = auth_client.get("/api/files/browse", params={"source": "onedrive"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "onedrive"
    assert payload["mock"] is True
    assert any(folder["id"] == "od-documents" for folder in payload["folders"])


def test_browse_onedrive_mock_folder_navigates(auth_client):
    response = auth_client.get(
        "/api/files/browse",
        params={"source": "onedrive", "item_id": "od-documents"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_item_id"] == "od-documents"
    assert payload["parent_item_id"] == "root"
    assert len(payload["files"]) >= 1
    assert payload["files"][0]["original_name"]
    assert payload["files"][0]["web_url"].startswith("https://")


def test_file_sources(auth_client):
    response = auth_client.get("/api/files/sources")
    assert response.status_code == 200
    sources = {entry["id"]: entry for entry in response.json()["sources"]}
    assert set(sources) == {"platform", "sharepoint", "onedrive"}
    assert sources["onedrive"]["mock"] is True
    assert sources["onedrive"]["outlook_connected"] is False
