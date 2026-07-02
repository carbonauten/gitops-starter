def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "content-hub"
    assert set(payload["supported_languages"]) == {"de", "en", "zh-CN"}


def test_i18n_bundle_de(client):
    response = client.get("/api/i18n/de")
    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "de"
    assert "errors.unauthorized" in payload["messages"]
