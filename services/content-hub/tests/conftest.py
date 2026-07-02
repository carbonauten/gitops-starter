import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ENTRA_MOCK_AUTH", "true")
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("AZURE_TENANT_ID", "")
    monkeypatch.setenv("AZURE_CLIENT_ID", "")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))

    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client):
    client.get("/api/auth/login", follow_redirects=False)
    return client


@pytest.fixture
def it_auth_client(client, monkeypatch):
    monkeypatch.setenv("IT_ADMIN_EMAILS", "demo@example.com")
    from app.config import get_settings

    get_settings.cache_clear()
    client.get("/api/auth/login", follow_redirects=False)
    yield client
    get_settings.cache_clear()


@pytest.fixture
def viewer_auth_client(client):
    client.get("/api/auth/login", follow_redirects=False)
    me = client.get("/api/auth/me").json()["user"]
    from app.database import UserAccount, _SessionLocal

    db = _SessionLocal()
    try:
        user = db.get(UserAccount, me["db_id"])
        user.role = "viewer"
        db.commit()
    finally:
        db.close()
    return client
