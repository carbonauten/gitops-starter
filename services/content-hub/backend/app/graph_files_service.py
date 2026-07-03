from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from .config import Settings, get_settings
from .graph_client import get_app_access_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _mock_browse(source: str, item_id: str | None) -> dict:
    if item_id in {None, "", "root"}:
        if source == "sharepoint":
            return {
                "source": source,
                "current_item_id": "root",
                "parent_item_id": None,
                "breadcrumbs": [{"id": "root", "name": "Firmendokumente"}],
                "folders": [
                    {"id": "sp-hr", "name": "HR", "source": source},
                    {"id": "sp-produktion", "name": "Produktion", "source": source},
                    {"id": "sp-vertrieb", "name": "Vertrieb", "source": source},
                ],
                "files": [
                    {
                        "id": "sp-file-1",
                        "name": "Organigramm.pdf",
                        "size_bytes": 245_000,
                        "content_type": "application/pdf",
                        "web_url": "mock://sharepoint/organigramm.pdf",
                        "source": source,
                    }
                ],
                "mock": True,
            }
        return {
            "source": source,
            "current_item_id": "root",
            "parent_item_id": None,
            "breadcrumbs": [{"id": "root", "name": "Mein OneDrive"}],
            "folders": [
                {"id": "od-documents", "name": "Dokumente", "source": source},
                {"id": "od-shared", "name": "Freigegeben", "source": source},
            ],
            "files": [
                {
                    "id": "od-file-1",
                    "name": "Notizen.docx",
                    "size_bytes": 88_000,
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "web_url": "mock://onedrive/notizen.docx",
                    "source": source,
                }
            ],
            "mock": True,
        }
    return {
        "source": source,
        "current_item_id": item_id,
        "parent_item_id": "root",
        "breadcrumbs": [
            {"id": "root", "name": "Firmendokumente" if source == "sharepoint" else "Mein OneDrive"},
            {"id": item_id, "name": item_id},
        ],
        "folders": [],
        "files": [],
        "mock": True,
    }


def _parse_sharepoint_site_path(site_url: str) -> str:
    parsed = urlparse(site_url.strip())
    hostname = parsed.netloc
    path = parsed.path.strip("/")
    if not hostname or not path:
        raise HTTPException(status_code=400, detail="sharepoint_not_configured")
    return f"{hostname}:/{path}"


async def _graph_get(path: str, settings: Settings | None = None) -> dict[str, Any]:
    token = await get_app_access_token(settings)
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            logger.error("Graph files request failed %s: %s", path, response.text)
            raise HTTPException(status_code=502, detail="graph_files_failed")
        return response.json()


def _map_drive_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    if "folder" in item:
        return {
            "id": item["id"],
            "name": item["name"],
            "source": source,
            "child_count": item.get("folder", {}).get("childCount"),
        }
    file_info = item.get("file", {})
    return {
        "id": item["id"],
        "name": item["name"],
        "size_bytes": int(item.get("size") or 0),
        "content_type": file_info.get("mimeType") or "application/octet-stream",
        "web_url": item.get("webUrl") or "",
        "modified_at": item.get("lastModifiedDateTime"),
        "source": source,
    }


def _split_drive_items(payload: dict[str, Any], source: str) -> tuple[list[dict], list[dict]]:
    folders: list[dict] = []
    files: list[dict] = []
    for item in payload.get("value", []):
        mapped = _map_drive_item(item, source)
        if "folder" in item:
            folders.append(mapped)
        else:
            files.append(mapped)
    folders.sort(key=lambda entry: entry["name"].lower())
    files.sort(key=lambda entry: entry["name"].lower())
    return folders, files


async def _resolve_sharepoint_drive_id(settings: Settings) -> str:
    if settings.sharepoint_drive_id.strip():
        return settings.sharepoint_drive_id.strip()
    site_key = _parse_sharepoint_site_path(settings.sharepoint_site_url)
    site = await _graph_get(f"/sites/{site_key}")
    if site.get("drive", {}).get("id"):
        return site["drive"]["id"]
    return (await _graph_get(f"/sites/{site['id']}/drive"))["id"]


async def browse_sharepoint(item_id: str | None = None, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if settings.files_browse_mock_mode or not settings.sharepoint_configured:
        return _mock_browse("sharepoint", item_id)

    drive_id = await _resolve_sharepoint_drive_id(settings)
    if not item_id or item_id == "root":
        path = f"/drives/{drive_id}/root/children"
        current_item_id = "root"
        parent_item_id = None
        breadcrumbs = [{"id": "root", "name": settings.sharepoint_display_name}]
    else:
        path = f"/drives/{drive_id}/items/{item_id}/children"
        current = await _graph_get(f"/drives/{drive_id}/items/{item_id}")
        current_item_id = item_id
        parent_item_id = current.get("parentReference", {}).get("id")
        breadcrumbs = [{"id": "root", "name": settings.sharepoint_display_name}]
        if current.get("name"):
            breadcrumbs.append({"id": current_item_id, "name": current["name"]})

    payload = await _graph_get(path)
    folders, files = _split_drive_items(payload, "sharepoint")
    return {
        "source": "sharepoint",
        "current_item_id": current_item_id,
        "parent_item_id": parent_item_id,
        "breadcrumbs": breadcrumbs,
        "folders": folders,
        "files": files,
        "mock": False,
    }


async def browse_onedrive(
    user_email: str,
    item_id: str | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    if settings.files_browse_mock_mode or not settings.graph_publish_configured:
        return _mock_browse("onedrive", item_id)

    normalized_email = user_email.strip()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="validation")

    if not item_id or item_id == "root":
        path = f"/users/{normalized_email}/drive/root/children"
        current_item_id = "root"
        parent_item_id = None
        breadcrumbs = [{"id": "root", "name": "OneDrive"}]
    else:
        path = f"/users/{normalized_email}/drive/items/{item_id}/children"
        current = await _graph_get(f"/users/{normalized_email}/drive/items/{item_id}")
        current_item_id = item_id
        parent_item_id = current.get("parentReference", {}).get("id")
        breadcrumbs = [{"id": "root", "name": "OneDrive"}]
        if current.get("name"):
            breadcrumbs.append({"id": current_item_id, "name": current["name"]})

    payload = await _graph_get(path)
    folders, files = _split_drive_items(payload, "onedrive")
    return {
        "source": "onedrive",
        "current_item_id": current_item_id,
        "parent_item_id": parent_item_id,
        "breadcrumbs": breadcrumbs,
        "folders": folders,
        "files": files,
        "mock": False,
    }
