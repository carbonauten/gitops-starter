import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plc_client import PLCClient, PLCConfig, _parse_address
from app import app, plc_client


def test_parse_address_holding():
    assert _parse_address("40001") == ("holding", 0)
    assert _parse_address("40002") == ("holding", 1)


def test_parse_address_coil():
    assert _parse_address("0") == ("coil", 0)
    assert _parse_address("1") == ("coil", 1)


def test_health_ok():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_get_plc_config_uses_client_config(monkeypatch):
    cfg = PLCConfig(host="192.168.1.10", port=502, unit_id=1)
    monkeypatch.setattr("app.plc_client", PLCClient(cfg))
    client = app.test_client()
    resp = client.get("/plc/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["host"] == "192.168.1.10"
    assert data["port"] == 502
    assert data["unit_id"] == 1


def test_plc_read_requires_address():
    client = app.test_client()
    resp = client.post("/plc/read", json={"type": "int"})
    assert resp.status_code == 400


def test_plc_read_returns_value(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.calls = []

        def read_tag(self, address, data_type):
            self.calls.append((address, data_type))
            return 123

    dummy = DummyClient()
    monkeypatch.setattr("app.plc_client", dummy)
    client = app.test_client()
    resp = client.post("/plc/read", json={"address": "40001", "type": "int"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["value"] == 123
    assert dummy.calls == [("40001", "int")]


def test_plc_write_accepts_value(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.calls = []

        def write_tag(self, address, data_type, value):
            self.calls.append((address, data_type, value))

    dummy = DummyClient()
    monkeypatch.setattr("app.plc_client", dummy)
    client = app.test_client()
    resp = client.post("/plc/write", json={"address": "40001", "type": "int", "value": 5})
    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "accepted"
    assert dummy.calls == [("40001", "int", 5)]


# --- GitHub bridge ---


def test_github_repos_returns_503_when_no_token(monkeypatch):
    monkeypatch.setattr("github_client.get_token", lambda: None)
    client = app.test_client()
    resp = client.get("/github/repos")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data.get("error") == "github_not_configured"


def test_github_repo_returns_repo_info(monkeypatch):
    def fake_get_repo(owner, repo):
        return 200, {"name": repo, "full_name": f"{owner}/{repo}", "default_branch": "main"}

    monkeypatch.setattr("app.get_repo", fake_get_repo)
    client = app.test_client()
    resp = client.get("/github/repo/carbonauten/gitops-starter")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "gitops-starter"
    assert data["default_branch"] == "main"


def test_github_workflow_dispatch_requires_params():
    client = app.test_client()
    resp = client.post("/github/workflow-dispatch", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert "owner" in data.get("message", "") or "missing" in data.get("error", "")


def test_github_workflow_dispatch_dispatches(monkeypatch):
    def fake_trigger(owner, repo, workflow_id, ref="main", inputs=None):
        return 200, {"status": "dispatched", "workflow_id": workflow_id}

    monkeypatch.setattr("app.trigger_workflow", fake_trigger)
    client = app.test_client()
    resp = client.post(
        "/github/workflow-dispatch",
        json={"owner": "carbonauten", "repo": "gitops-starter", "workflow_id": "ci.yml"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "dispatched"
    assert data["workflow_id"] == "ci.yml"


def test_github_latest_release_returns_release(monkeypatch):
    def fake_latest(owner, repo):
        return 200, {"tag_name": "v1.0.0", "name": "Release 1.0", "published_at": "2024-01-01T00:00:00Z"}

    monkeypatch.setattr("app.get_latest_release", fake_latest)
    client = app.test_client()
    resp = client.get("/github/releases/carbonauten/gitops-starter/latest")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["tag_name"] == "v1.0.0"
    assert data["name"] == "Release 1.0"
