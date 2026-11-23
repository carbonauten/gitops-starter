"""WordPress's own REST API (wp-json/), for managing a site that's already
installed and running - as opposed to strato_login_session.py /
wordpress_automation_service.py, which only cover *provisioning* a new
WordPress install through Strato's hosting panel (something WordPress
itself has no say in). Every modern WordPress core ships this API and
"Application Passwords" (core feature since WP 5.6, Settings > Users >
Profile > Application Passwords in wp-admin) for authenticating to it -
no browser automation, no CAPTCHA, just HTTP Basic Auth with the app
password as the password. Much more reliable than the Strato automation,
but requires the site owner to generate and register an Application
Password for each site manually (see wordpress_site_config_service.py).

Note: the WP core REST API's /wp/v2/plugins routes support listing,
activating/deactivating and installing a *new* plugin by slug - there is
no core route to trigger "update an installed plugin to the latest
version" (that only exists in the wp-admin UI's AJAX flow and WP-CLI,
neither of which this integration drives). set_plugin_status() below is
therefore limited to activate/deactivate, not "update".
"""

from __future__ import annotations

import html
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .wordpress_site_config_service import WordPressSiteCredentials

logger = logging.getLogger(__name__)

_TIMEOUT = 20.0


def _client(creds: WordPressSiteCredentials) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=creds.base_url,
        auth=(creds.username, creds.app_password),
        timeout=_TIMEOUT,
    )


async def _get(client: httpx.AsyncClient, path: str, **kwargs: Any) -> httpx.Response:
    try:
        response = await client.get(path, **kwargs)
    except httpx.HTTPError as exc:
        logger.warning("WordPress site unreachable: %s", exc)
        raise HTTPException(status_code=502, detail="wordpress_site_unreachable") from exc
    if response.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="wordpress_site_unauthorized")
    if response.status_code >= 400:
        logger.warning("WordPress REST request failed: %s %s -> %s", path, response.status_code, response.text[:300])
        raise HTTPException(status_code=502, detail="wordpress_site_request_failed")
    return response


async def _post(client: httpx.AsyncClient, path: str, json: dict[str, Any]) -> httpx.Response:
    try:
        response = await client.post(path, json=json)
    except httpx.HTTPError as exc:
        logger.warning("WordPress site unreachable: %s", exc)
        raise HTTPException(status_code=502, detail="wordpress_site_unreachable") from exc
    if response.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="wordpress_site_unauthorized")
    if response.status_code >= 400:
        logger.warning("WordPress REST request failed: %s %s -> %s", path, response.status_code, response.text[:300])
        raise HTTPException(status_code=502, detail="wordpress_site_request_failed")
    return response


async def check_site_status(creds: WordPressSiteCredentials) -> dict[str, Any]:
    async with _client(creds) as client:
        root = await _get(client, "/wp-json/")
        root_payload = root.json() if root.headers.get("content-type", "").startswith("application/json") else {}
        me = await _get(client, "/wp-json/wp/v2/users/me", params={"context": "edit"})
        me_payload = me.json()
    return {
        "reachable": True,
        "site_name": root_payload.get("name") or urlparse(creds.base_url).netloc,
        "connected_as": me_payload.get("name") or creds.username,
        "roles": me_payload.get("roles") or [],
    }


def _post_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": html.unescape((item.get("title") or {}).get("rendered") or ""),
        "status": item.get("status"),
        "link": item.get("link") or "",
        "date": item.get("date") or "",
    }


async def list_posts(creds: WordPressSiteCredentials, *, status: str = "any", per_page: int = 20) -> list[dict[str, Any]]:
    async with _client(creds) as client:
        response = await _get(
            client,
            "/wp-json/wp/v2/posts",
            params={"context": "edit", "status": status, "per_page": per_page, "orderby": "date", "order": "desc"},
        )
    return [_post_summary(item) for item in response.json()]


async def create_post(creds: WordPressSiteCredentials, *, title: str, content: str, status: str) -> dict[str, Any]:
    async with _client(creds) as client:
        response = await _post(client, "/wp-json/wp/v2/posts", {"title": title, "content": content, "status": status})
    return _post_summary(response.json())


async def update_post(creds: WordPressSiteCredentials, post_id: int, **fields: Any) -> dict[str, Any]:
    async with _client(creds) as client:
        response = await _post(client, f"/wp-json/wp/v2/posts/{post_id}", fields)
    return _post_summary(response.json())


def _plugin_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "plugin": item.get("plugin") or "",
        "name": html.unescape(item.get("name") or ""),
        "version": item.get("version") or "",
        "status": item.get("status") or "inactive",
    }


async def list_plugins(creds: WordPressSiteCredentials) -> list[dict[str, Any]]:
    async with _client(creds) as client:
        response = await _get(client, "/wp-json/wp/v2/plugins")
    return [_plugin_summary(item) for item in response.json()]


async def set_plugin_status(creds: WordPressSiteCredentials, plugin: str, status: str) -> dict[str, Any]:
    if status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="validation")
    async with _client(creds) as client:
        response = await _post(client, f"/wp-json/wp/v2/plugins/{plugin}", {"status": status})
    return _plugin_summary(response.json())
