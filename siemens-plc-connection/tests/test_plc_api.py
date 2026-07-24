from plc_client import PLCClient, PLCConfig
from app import app, plc_client


def test_health_ok():
    client = app.test_client()
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_get_plc_config_uses_client_config(monkeypatch):
    cfg = PLCConfig(host="10.0.0.5", rack=0, slot=1)
    monkeypatch.setattr("app.plc_client", PLCClient(cfg))

    client = app.test_client()
    resp = client.get("/plc/config")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["host"] == "10.0.0.5"
    assert data["rack"] == 0
    assert data["slot"] == 1


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
    resp = client.post("/plc/read", json={"address": "DB1.DBW0", "type": "int"})

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["value"] == 123
    assert dummy.calls == [("DB1.DBW0", "int")]


def test_plc_write_accepts_value(monkeypatch):
    class DummyClient:
        def __init__(self):
            self.calls = []

        def write_tag(self, address, data_type, value):
            self.calls.append((address, data_type, value))

    dummy = DummyClient()
    monkeypatch.setattr("app.plc_client", dummy)

    client = app.test_client()
    resp = client.post(
        "/plc/write", json={"address": "DB1.DBW0", "type": "int", "value": 5}
    )

    assert resp.status_code == 202
    data = resp.get_json()
    assert data["status"] == "accepted"
    assert dummy.calls == [("DB1.DBW0", "int", 5)]

