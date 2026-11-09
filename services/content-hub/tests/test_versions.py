def test_article_update_creates_revision(auth_client):
    created = auth_client.post("/api/articles", json={"title": "Versioned", "content": "<p>v1</p>"})
    article_id = created.json()["article"]["id"]

    # Initial create already stores version 1
    versions = auth_client.get(f"/api/versions/article/{article_id}")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) == 1

    auth_client.patch(
        f"/api/articles/{article_id}",
        json={"title": "Versioned v2", "content": "<p>v2</p>"},
    )

    versions = auth_client.get(f"/api/versions/article/{article_id}")
    assert versions.status_code == 200
    items = versions.json()["versions"]
    assert len(items) == 2
    assert items[0]["version_number"] == 2
    assert items[0]["changed_by_name"]


def test_compare_article_version_with_current(auth_client):
    created = auth_client.post("/api/articles", json={"title": "Compare me", "content": "<p>old</p>"})
    article_id = created.json()["article"]["id"]
    auth_client.patch(f"/api/articles/{article_id}", json={"content": "<p>new</p>"})

    compare = auth_client.get(f"/api/versions/article/{article_id}/compare?from_version=1")
    assert compare.status_code == 200
    payload = compare.json()
    assert payload["to_version"] == "current"
    fields = {change["field"] for change in payload["changes"]}
    assert "content" in fields


def test_compare_article_content_includes_word_level_diff(auth_client):
    created = auth_client.post(
        "/api/articles",
        json={"title": "Diff me", "content": "<p>The quick brown fox jumps.</p>"},
    )
    article_id = created.json()["article"]["id"]
    auth_client.patch(
        f"/api/articles/{article_id}",
        json={"content": "<p>The quick red fox jumps high.</p>"},
    )

    compare = auth_client.get(f"/api/versions/article/{article_id}/compare?from_version=1")
    assert compare.status_code == 200
    content_change = next(c for c in compare.json()["changes"] if c["field"] == "content")
    assert "diff" in content_change

    segments = content_change["diff"]
    ops = {segment["op"] for segment in segments}
    assert "delete" in ops
    assert "insert" in ops
    assert "equal" in ops
    # Reassembling "before" from equal+delete segments and "after" from
    # equal+insert segments must reproduce the original strings exactly.
    before = "".join(s["text"] for s in segments if s["op"] in ("equal", "delete"))
    after = "".join(s["text"] for s in segments if s["op"] in ("equal", "insert"))
    assert before == "<p>The quick brown fox jumps.</p>"
    assert after == "<p>The quick red fox jumps high.</p>"


def test_compare_certificate_notes_includes_word_level_diff(auth_client):
    created = auth_client.post(
        "/api/certificates",
        json={
            "name": "Diff Cert",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-01-01",
            "responsible_name": "QA",
            "responsible_email": "qa@example.com",
            "notes": "Initial notes about the audit",
        },
    )
    certificate_id = created.json()["certificate"]["id"]
    auth_client.patch(
        f"/api/certificates/{certificate_id}",
        json={"notes": "Updated notes about the external audit"},
    )

    compare = auth_client.get(f"/api/versions/certificate/{certificate_id}/compare?from_version=1")
    assert compare.status_code == 200
    notes_change = next(c for c in compare.json()["changes"] if c["field"] == "notes")
    assert "diff" in notes_change
    assert any(segment["op"] == "insert" and "external" in segment["text"] for segment in notes_change["diff"])


def test_compare_does_not_full_diff_non_text_fields(auth_client):
    created = auth_client.post("/api/articles", json={"title": "A", "content": "<p>x</p>"})
    article_id = created.json()["article"]["id"]
    auth_client.patch(f"/api/articles/{article_id}", json={"title": "B"})

    compare = auth_client.get(f"/api/versions/article/{article_id}/compare?from_version=1")
    title_change = next(c for c in compare.json()["changes"] if c["field"] == "title")
    assert "diff" not in title_change


def test_certificate_update_creates_revision(auth_client):
    created = auth_client.post(
        "/api/certificates",
        json={
            "name": "ISO 9001",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-01-01",
            "responsible_name": "QA",
            "responsible_email": "qa@example.com",
        },
    )
    certificate_id = created.json()["certificate"]["id"]
    auth_client.patch(f"/api/certificates/{certificate_id}", json={"notes": "Updated notes"})

    versions = auth_client.get(f"/api/versions/certificate/{certificate_id}")
    assert versions.status_code == 200
    assert len(versions.json()["versions"]) == 2


def test_restore_article_version(auth_client):
    created = auth_client.post("/api/articles", json={"title": "Original", "content": "<p>one</p>"})
    article_id = created.json()["article"]["id"]
    auth_client.patch(f"/api/articles/{article_id}", json={"title": "Changed", "content": "<p>two</p>"})

    restore = auth_client.post(f"/api/versions/article/{article_id}/restore/1")
    assert restore.status_code == 200
    assert restore.json()["restored_version"] == 1

    article = auth_client.get(f"/api/articles/{article_id}").json()["article"]
    assert article["title"] == "Original"
    assert "<p>one</p>" in article["content"]

    versions = auth_client.get(f"/api/versions/article/{article_id}").json()["versions"]
    assert len(versions) >= 3  # create + pre-update + pre-restore


def test_restore_certificate_version(auth_client):
    created = auth_client.post(
        "/api/certificates",
        json={
            "name": "Restore Cert",
            "category": "compliance",
            "issuer": "TÜV",
            "valid_from": "2025-01-01",
            "valid_to": "2026-01-01",
            "responsible_name": "QA",
            "responsible_email": "qa@example.com",
            "notes": "v1 notes",
        },
    )
    certificate_id = created.json()["certificate"]["id"]
    auth_client.patch(f"/api/certificates/{certificate_id}", json={"notes": "v2 notes", "name": "Changed Cert"})

    restore = auth_client.post(f"/api/versions/certificate/{certificate_id}/restore/1")
    assert restore.status_code == 200

    certificate = auth_client.get(f"/api/certificates/{certificate_id}").json()["certificate"]
    assert certificate["name"] == "Restore Cert"
    assert certificate["notes"] == "v1 notes"
