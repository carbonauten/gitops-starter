import sys
from pathlib import Path

import pytest
from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

TEST_PASSWORD = "test-password-123"
TEST_EMAIL = "demo@example.com"


@pytest.fixture(autouse=True)
def test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ENTRA_MOCK_AUTH", "false")
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


def _seed_password_user(email: str = TEST_EMAIL, role: str = "editor") -> None:
    from app.database import UserAccount, _SessionLocal
    from app.password_service import hash_password

    db = _SessionLocal()
    try:
        user = db.scalar(select(UserAccount).where(UserAccount.email == email))
        if user is None:
            user = UserAccount(
                entra_id="test-user-001",
                email=email,
                name="Demo User",
                role=role,
                password_hash=hash_password(TEST_PASSWORD),
                is_active=True,
            )
            db.add(user)
        else:
            user.password_hash = hash_password(TEST_PASSWORD)
            user.role = role
            user.is_active = True
        db.commit()
    finally:
        db.close()


def _login(client, email: str = TEST_EMAIL, password: str = TEST_PASSWORD):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response


@pytest.fixture
def auth_client(client):
    _seed_password_user()
    _login(client)
    return client


@pytest.fixture
def it_auth_client(client, monkeypatch):
    monkeypatch.setenv("IT_ADMIN_EMAILS", TEST_EMAIL)
    from app.config import get_settings

    get_settings.cache_clear()
    _seed_password_user(role="editor")
    _login(client)
    yield client
    get_settings.cache_clear()


@pytest.fixture
def viewer_auth_client(client):
    _seed_password_user(role="viewer")
    _login(client)
    return client
