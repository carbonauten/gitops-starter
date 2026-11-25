import pytest

from app.wopi_service import _locks, mint_wopi_token


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


def test_wopi_requires_access_token(client, db_session):
    file_asset = _make_file_asset(db_session)
    response = client.get(f"/wopi/files/{file_asset.id}")
    assert response.status_code == 401


def test_wopi_check_file_info_with_valid_token(client, db_session):
    file_asset = _make_file_asset(db_session, content=b"abc")
    token = mint_wopi_token(file_asset.id, user_id="u1", user_name="Mike")
    response = client.get(f"/wopi/files/{file_asset.id}", params={"access_token": token})
    assert response.status_code == 200
    payload = response.json()
    assert payload["BaseFileName"] == "report.docx"
    assert payload["Size"] == 3


def test_wopi_get_and_put_contents_roundtrip(client, db_session):
    file_asset = _make_file_asset(db_session, content=b"old content")
    token = mint_wopi_token(file_asset.id, user_id="u1", user_name="Mike")

    got = client.get(f"/wopi/files/{file_asset.id}/contents", params={"access_token": token})
    assert got.status_code == 200
    assert got.content == b"old content"

    put = client.post(
        f"/wopi/files/{file_asset.id}/contents",
        params={"access_token": token},
        content=b"new content",
    )
    assert put.status_code == 200

    got_again = client.get(f"/wopi/files/{file_asset.id}/contents", params={"access_token": token})
    assert got_again.content == b"new content"


def test_wopi_lock_then_conflicting_put_is_rejected(client, db_session):
    file_asset = _make_file_asset(db_session)
    token = mint_wopi_token(file_asset.id, user_id="u1", user_name="Mike")

    locked = client.post(
        f"/wopi/files/{file_asset.id}",
        params={"access_token": token},
        headers={"X-WOPI-Override": "LOCK", "X-WOPI-Lock": "lock-a"},
    )
    assert locked.status_code == 200
    assert locked.headers["X-WOPI-Lock"] == "lock-a"

    conflicting_put = client.post(
        f"/wopi/files/{file_asset.id}/contents",
        params={"access_token": token},
        headers={"X-WOPI-Lock": "lock-b"},
        content=b"should not apply",
    )
    assert conflicting_put.status_code == 409


def test_wopi_token_scoped_to_its_own_file_id(client, db_session):
    file_a = _make_file_asset(db_session)
    file_b = _make_file_asset(db_session)
    token_for_a = mint_wopi_token(file_a.id, user_id="u1", user_name="Mike")

    response = client.get(f"/wopi/files/{file_b.id}", params={"access_token": token_for_a})
    assert response.status_code == 401
