from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.wordpress_rest_service import (
    check_site_status,
    create_post,
    list_plugins,
    list_posts,
    set_plugin_status,
    update_post,
)
from app.wordpress_site_config_service import WordPressSiteCredentials

CREDS = WordPressSiteCredentials(
    id="site-1", label="Test Site", base_url="https://example.com", username="admin", app_password="xxxx xxxx xxxx xxxx"
)


def _patch_client(monkeypatch, handler):
    def _fake_client(creds):
        transport = httpx.MockTransport(handler)
        return httpx.AsyncClient(base_url=creds.base_url, transport=transport)

    monkeypatch.setattr("app.wordpress_rest_service._client", _fake_client)


def test_check_site_status_success(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/":
            return httpx.Response(200, json={"name": "My Blog"})
        if request.url.path == "/wp-json/wp/v2/users/me":
            return httpx.Response(200, json={"name": "Admin User", "roles": ["administrator"]})
        return httpx.Response(404)

    _patch_client(monkeypatch, handler)
    result = asyncio.run(check_site_status(CREDS))
    assert result["reachable"] is True
    assert result["site_name"] == "My Blog"
    assert result["connected_as"] == "Admin User"
    assert result["roles"] == ["administrator"]


def test_check_site_status_wrong_credentials(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/wp-json/":
            return httpx.Response(200, json={"name": "My Blog"})
        return httpx.Response(401, json={"code": "rest_not_logged_in"})

    _patch_client(monkeypatch, handler)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(check_site_status(CREDS))
    assert exc_info.value.detail == "wordpress_site_unauthorized"


def test_check_site_status_unreachable(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_client(monkeypatch, handler)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(check_site_status(CREDS))
    assert exc_info.value.detail == "wordpress_site_unreachable"


def test_list_posts_maps_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wp/v2/posts"
        assert request.url.params["status"] == "any"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 42,
                    "title": {"rendered": "Hello &amp; Welcome"},
                    "status": "publish",
                    "link": "https://example.com/hello",
                    "date": "2026-11-23T10:00:00",
                }
            ],
        )

    _patch_client(monkeypatch, handler)
    posts = asyncio.run(list_posts(CREDS))
    assert posts == [
        {"id": 42, "title": "Hello & Welcome", "status": "publish", "link": "https://example.com/hello", "date": "2026-11-23T10:00:00"}
    ]


def test_create_post_sends_expected_body(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(
            201,
            json={"id": 7, "title": {"rendered": "New Post"}, "status": "draft", "link": "", "date": ""},
        )

    _patch_client(monkeypatch, handler)
    post = asyncio.run(create_post(CREDS, title="New Post", content="Body text", status="draft"))
    assert post["id"] == 7
    assert b'"title"' in captured["body"]
    assert b'"draft"' in captured["body"]


def test_update_post_only_sends_provided_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wp/v2/posts/7"
        return httpx.Response(200, json={"id": 7, "title": {"rendered": "Updated"}, "status": "publish", "link": "", "date": ""})

    _patch_client(monkeypatch, handler)
    post = asyncio.run(update_post(CREDS, 7, status="publish"))
    assert post["status"] == "publish"


def test_list_plugins_maps_fields(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wp/v2/plugins"
        return httpx.Response(
            200,
            json=[{"plugin": "hello-dolly/hello", "name": "Hello Dolly", "version": "1.7.2", "status": "inactive"}],
        )

    _patch_client(monkeypatch, handler)
    plugins = asyncio.run(list_plugins(CREDS))
    assert plugins == [{"plugin": "hello-dolly/hello", "name": "Hello Dolly", "version": "1.7.2", "status": "inactive"}]


def test_set_plugin_status_activate(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/wp-json/wp/v2/plugins/hello-dolly/hello"
        return httpx.Response(200, json={"plugin": "hello-dolly/hello", "name": "Hello Dolly", "version": "1.7.2", "status": "active"})

    _patch_client(monkeypatch, handler)
    result = asyncio.run(set_plugin_status(CREDS, "hello-dolly/hello", "active"))
    assert result["status"] == "active"


def test_set_plugin_status_rejects_invalid_status():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(set_plugin_status(CREDS, "hello-dolly/hello", "deleted"))
    assert exc_info.value.status_code == 400
