import json

from app import app


def test_root_returns_hello_message():
    client = app.test_client()
    response = client.get("/")

    assert response.status_code == 200

    data = json.loads(response.data.decode("utf-8"))
    assert data == {"message": "Hello from example-service"}

