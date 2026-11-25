import hashlib

import pytest

from app.wopi_service import (
    _locks,
    check_file_info,
    collabora_edit_url,
    get_file_contents,
    get_lock,
    lock,
    mint_wopi_token,
    parse_wopi_token,
    put_file,
    refresh_lock,
    unlock,
)


@pytest.fixture
def db_session(client):
    from app import database

    db = database._SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clear_locks():
    _locks.clear()
    yield
    _locks.clear()


def _make_file_asset(db_session, content: bytes = b"hello world"):
    from app.database import FileAsset
    from app.storage import save_upload

    stored_name, storage_path, _ = save_upload(content, "report.docx")
    file_asset = FileAsset(
        original_name="report.docx",
        stored_name=stored_name,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=len(content),
        storage_path=storage_path,
        uploaded_by_id="user-1",
        uploaded_by_name="Mike",
    )
    db_session.add(file_asset)
    db_session.commit()
    db_session.refresh(file_asset)
    return file_asset


def test_mint_and_parse_wopi_token_roundtrip():
    token = mint_wopi_token("file-1", user_id="user-1", user_name="Mike")
    payload = parse_wopi_token(token)
    assert payload["file_id"] == "file-1"
    assert payload["user_id"] == "user-1"
    assert payload["user_name"] == "Mike"


def test_parse_wopi_token_rejects_tampered_value():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        parse_wopi_token("not-a-real-token")


def test_check_file_info_reports_size_and_version(db_session):
    file_asset = _make_file_asset(db_session, content=b"hello world")
    info = check_file_info(db_session, file_id=file_asset.id, token_payload={"user_id": "u1", "user_name": "Mike"})
    assert info["BaseFileName"] == "report.docx"
    assert info["Size"] == len(b"hello world")
    assert info["Version"] == hashlib.md5(b"hello world").hexdigest()[:16]
    assert info["UserFriendlyName"] == "Mike"


def test_get_file_contents_returns_bytes(db_session):
    file_asset = _make_file_asset(db_session, content=b"original content")
    assert get_file_contents(db_session, file_id=file_asset.id) == b"original content"


def test_put_file_without_lock_overwrites_and_updates_size(db_session):
    file_asset = _make_file_asset(db_session, content=b"old")
    status = put_file(db_session, file_id=file_asset.id, content=b"much longer new content", provided_lock="")
    assert status == 200
    assert get_file_contents(db_session, file_id=file_asset.id) == b"much longer new content"
    db_session.refresh(file_asset)
    assert file_asset.size_bytes == len(b"much longer new content")


def test_put_file_conflicts_when_locked_by_someone_else(db_session):
    file_asset = _make_file_asset(db_session)
    lock(file_asset.id, new_lock="lock-a")
    status = put_file(db_session, file_id=file_asset.id, content=b"attempted overwrite", provided_lock="lock-b")
    assert status == 409


def test_put_file_succeeds_with_matching_lock(db_session):
    file_asset = _make_file_asset(db_session)
    lock(file_asset.id, new_lock="lock-a")
    status = put_file(db_session, file_id=file_asset.id, content=b"edited", provided_lock="lock-a")
    assert status == 200


def test_lock_lifecycle():
    status, current = lock("file-x", new_lock="lock-1")
    assert (status, current) == (200, "lock-1")
    assert get_lock("file-x") == "lock-1"

    # same lock id re-locking (Collabora's own retry) succeeds
    status, current = lock("file-x", new_lock="lock-1")
    assert (status, current) == (200, "lock-1")

    # a different lock id while locked is a conflict
    status, current = lock("file-x", new_lock="lock-2")
    assert (status, current) == (409, "lock-1")

    status, current = refresh_lock("file-x", expected_lock="lock-1")
    assert (status, current) == (200, "lock-1")

    status, current = unlock("file-x", expected_lock="lock-2")
    assert (status, current) == (409, "lock-1")

    status, current = unlock("file-x", expected_lock="lock-1")
    assert (status, current) == (200, "")
    assert get_lock("file-x") == ""


def test_collabora_edit_url_none_when_not_configured(db_session, monkeypatch):
    monkeypatch.setenv("COLLABORA_URL", "")
    from app.config import get_settings

    get_settings.cache_clear()
    file_asset = _make_file_asset(db_session)
    assert collabora_edit_url(file_asset, user_id="u1", user_name="Mike") is None
    get_settings.cache_clear()


def test_collabora_edit_url_builds_wopisrc_and_token(db_session, monkeypatch):
    monkeypatch.setenv("COLLABORA_URL", "https://collabora.example.com")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://hub.example.com")
    from app.config import get_settings

    get_settings.cache_clear()
    file_asset = _make_file_asset(db_session)
    url = collabora_edit_url(file_asset, user_id="u1", user_name="Mike")
    assert url is not None
    assert url.startswith("https://collabora.example.com/browser/dist/cool.html?")
    assert "WOPISrc=https%3A%2F%2Fhub.example.com%2Fwopi%2Ffiles%2F" in url
    assert "access_token=" in url
    get_settings.cache_clear()
