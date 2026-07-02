def test_mock_login_and_profile(client):
    login = client.get("/api/auth/login", follow_redirects=False)
    assert login.status_code == 302

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    user = me.json()["user"]
    assert user["email"] == "demo@example.com"
    assert user["name"] == "Demo User"


def test_language_preference_persists_in_session(client):
    client.get("/api/auth/login", follow_redirects=False)

    response = client.patch("/api/user/language", json={"language": "zh-CN"})
    assert response.status_code == 200
    assert response.json()["user"]["language"] == "zh-CN"

    me = client.get("/api/auth/me")
    assert me.json()["user"]["language"] == "zh-CN"


def test_unauthorized_without_session(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_logout_clears_session(client):
    client.get("/api/auth/login", follow_redirects=False)
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204

    me = client.get("/api/auth/me")
    assert me.status_code == 401
