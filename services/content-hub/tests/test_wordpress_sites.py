from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException


def test_editor_cannot_list_sites(auth_client):
    response = auth_client.get("/api/wordpress/sites")
    assert response.status_code == 403


def test_viewer_cannot_list_sites(viewer_auth_client):
    response = viewer_auth_client.get("/api/wordpress/sites")
    assert response.status_code == 403


def test_designer_sees_empty_site_list(designer_auth_client):
    response = designer_auth_client.get("/api/wordpress/sites")
    assert response.status_code == 200
    assert response.json()["sites"] == []


def test_create_list_and_delete_site(designer_auth_client):
    created = designer_auth_client.post(
        "/api/wordpress/sites",
        json={
            "label": "My Blog",
            "base_url": "https://example.com",
            "username": "admin",
            "app_password": "xxxx xxxx xxxx xxxx xxxx xxxx",
        },
    )
    assert created.status_code == 201
    site = created.json()["site"]
    assert site["label"] == "My Blog"
    assert site["base_url"] == "https://example.com"
    assert "app_password" not in site
    assert "app_password_enc" not in site

    listed = designer_auth_client.get("/api/wordpress/sites")
    assert len(listed.json()["sites"]) == 1

    deleted = designer_auth_client.delete(f"/api/wordpress/sites/{site['id']}")
    assert deleted.status_code == 204

    listed_after = designer_auth_client.get("/api/wordpress/sites")
    assert listed_after.json()["sites"] == []


def test_create_site_requires_valid_url(designer_auth_client):
    response = designer_auth_client.post(
        "/api/wordpress/sites",
        json={"label": "Bad", "base_url": "not-a-url", "username": "admin", "app_password": "x"},
    )
    assert response.status_code == 400


def test_create_site_strips_trailing_slash(designer_auth_client):
    created = designer_auth_client.post(
        "/api/wordpress/sites",
        json={"label": "Trail", "base_url": "https://example.com/", "username": "admin", "app_password": "x"},
    )
    assert created.json()["site"]["base_url"] == "https://example.com"


def test_delete_unknown_site_404s(designer_auth_client):
    response = designer_auth_client.delete("/api/wordpress/sites/does-not-exist")
    assert response.status_code == 404


def _create_site(client) -> str:
    created = client.post(
        "/api/wordpress/sites",
        json={"label": "My Blog", "base_url": "https://example.com", "username": "admin", "app_password": "x"},
    )
    return created.json()["site"]["id"]


def test_get_site_status_surfaces_result(designer_auth_client):
    site_id = _create_site(designer_auth_client)

    async def _fake_status(creds):
        assert creds.base_url == "https://example.com"
        return {"reachable": True, "site_name": "My Blog", "connected_as": "Admin", "roles": ["administrator"]}

    with patch("app.routes.wordpress_sites.check_site_status", side_effect=_fake_status):
        response = designer_auth_client.get(f"/api/wordpress/sites/{site_id}/status")
    assert response.status_code == 200
    assert response.json()["site_name"] == "My Blog"


def test_get_site_status_surfaces_translated_error(designer_auth_client):
    site_id = _create_site(designer_auth_client)

    async def _fake_status(creds):
        raise HTTPException(status_code=502, detail="wordpress_site_unauthorized")

    with patch("app.routes.wordpress_sites.check_site_status", side_effect=_fake_status):
        response = designer_auth_client.get(f"/api/wordpress/sites/{site_id}/status")
    assert response.status_code == 502
    assert response.json()["code"] == "wordpress_site_unauthorized"


def test_list_and_create_posts(designer_auth_client):
    site_id = _create_site(designer_auth_client)

    async def _fake_list(creds, status="any"):
        return [{"id": 1, "title": "Hi", "status": "publish", "link": "", "date": ""}]

    with patch("app.routes.wordpress_sites.list_posts", side_effect=_fake_list):
        response = designer_auth_client.get(f"/api/wordpress/sites/{site_id}/posts")
    assert response.status_code == 200
    assert response.json()["posts"][0]["title"] == "Hi"

    async def _fake_create(creds, *, title, content, status):
        assert title == "New"
        return {"id": 2, "title": "New", "status": "draft", "link": "", "date": ""}

    with patch("app.routes.wordpress_sites.create_post", side_effect=_fake_create):
        response = designer_auth_client.post(
            f"/api/wordpress/sites/{site_id}/posts",
            json={"title": "New", "content": "Body", "status": "draft"},
        )
    assert response.status_code == 201
    assert response.json()["post"]["id"] == 2


def test_update_post_only_forwards_provided_fields(designer_auth_client):
    site_id = _create_site(designer_auth_client)
    captured = {}

    async def _fake_update(creds, post_id, **fields):
        captured["post_id"] = post_id
        captured["fields"] = fields
        return {"id": post_id, "title": "x", "status": fields.get("status", "draft"), "link": "", "date": ""}

    with patch("app.routes.wordpress_sites.update_post", side_effect=_fake_update):
        response = designer_auth_client.patch(f"/api/wordpress/sites/{site_id}/posts/9", json={"status": "publish"})
    assert response.status_code == 200
    assert captured["post_id"] == 9
    assert captured["fields"] == {"status": "publish"}


def test_list_and_toggle_plugins(designer_auth_client):
    site_id = _create_site(designer_auth_client)

    async def _fake_list(creds):
        return [{"plugin": "hello-dolly/hello", "name": "Hello Dolly", "version": "1.7.2", "status": "inactive"}]

    with patch("app.routes.wordpress_sites.list_plugins", side_effect=_fake_list):
        response = designer_auth_client.get(f"/api/wordpress/sites/{site_id}/plugins")
    assert response.status_code == 200
    assert response.json()["plugins"][0]["plugin"] == "hello-dolly/hello"

    async def _fake_set_status(creds, plugin, status):
        assert plugin == "hello-dolly/hello"
        assert status == "active"
        return {"plugin": plugin, "name": "Hello Dolly", "version": "1.7.2", "status": "active"}

    with patch("app.routes.wordpress_sites.set_plugin_status", side_effect=_fake_set_status):
        response = designer_auth_client.patch(
            f"/api/wordpress/sites/{site_id}/plugins/hello-dolly/hello",
            json={"status": "active"},
        )
    assert response.status_code == 200
    assert response.json()["plugin"]["status"] == "active"
