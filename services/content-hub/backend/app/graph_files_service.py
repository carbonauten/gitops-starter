from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .graph_client import get_app_access_token
from .outlook_service import get_outlook_access_token

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Nested mock content so folder buttons navigate to sample files (not empty).
_MOCK_CHILDREN: dict[str, dict[str, list[dict[str, Any]]]] = {
    "od-documents": {
        "folders": [{"id": "od-docs-work", "name": "Arbeit", "source": "onedrive"}],
        "files": [
            {
                "id": "od-file-docs-1",
                "name": "Projektplan.docx",
                "original_name": "Projektplan.docx",
                "size_bytes": 42_000,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "web_url": "https://www.office.com",
                "source": "onedrive",
            }
        ],
    },
    "od-shared": {
        "folders": [],
        "files": [
            {
                "id": "od-file-shared-1",
                "name": "Team-Notiz.pdf",
                "original_name": "Team-Notiz.pdf",
                "size_bytes": 120_000,
                "content_type": "application/pdf",
                "web_url": "https://www.office.com",
                "source": "onedrive",
            }
        ],
    },
    "od-docs-work": {
        "folders": [],
        "files": [
            {
                "id": "od-file-work-1",
                "name": "Wochenbericht.xlsx",
                "original_name": "Wochenbericht.xlsx",
                "size_bytes": 18_500,
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "web_url": "https://www.office.com",
                "source": "onedrive",
            }
        ],
    },
    "sp-hr": {
        "folders": [],
        "files": [
            {
                "id": "sp-file-hr-1",
                "name": "Mitarbeiterhandbuch.pdf",
                "original_name": "Mitarbeiterhandbuch.pdf",
                "size_bytes": 510_000,
                "content_type": "application/pdf",
                "web_url": "https://www.office.com",
                "source": "sharepoint",
            }
        ],
    },
    "sp-produktion": {
        "folders": [],
        "files": [
            {
                "id": "sp-file-prod-1",
                "name": "Prozessbeschreibung.docx",
                "original_name": "Prozessbeschreibung.docx",
                "size_bytes": 95_000,
                "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "web_url": "https://www.office.com",
                "source": "sharepoint",
            }
        ],
    },
    "sp-vertrieb": {
        "folders": [],
        "files": [
            {
                "id": "sp-file-sales-1",
                "name": "Preisblatt.xlsx",
                "original_name": "Preisblatt.xlsx",
                "size_bytes": 33_000,
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "web_url": "https://www.office.com",
                "source": "sharepoint",
            }
        ],
    },
}

_MOCK_PARENT: dict[str, str] = {
    "od-documents": "root",
    "od-shared": "root",
    "od-docs-work": "od-documents",
    "sp-hr": "root",
    "sp-produktion": "root",
    "sp-vertrieb": "root",
}

_MOCK_NAMES: dict[str, str] = {
    "od-documents": "Dokumente",
    "od-shared": "Freigegeben",
    "od-docs-work": "Arbeit",
    "sp-hr": "HR",
    "sp-produktion": "Produktion",
    "sp-vertrieb": "Vertrieb",
}


def _mock_browse(source: str, item_id: str | None) -> dict:
    root_name = "Firmendokumente" if source == "sharepoint" else "Mein OneDrive"
    if item_id in {None, "", "root"}:
        if source == "sharepoint":
            return {
                "source": source,
                "current_item_id": "root",
                "parent_item_id": None,
                "breadcrumbs": [{"id": "root", "name": root_name}],
                "folders": [
                    {"id": "sp-hr", "name": "HR", "source": source},
                    {"id": "sp-produktion", "name": "Produktion", "source": source},
                    {"id": "sp-vertrieb", "name": "Vertrieb", "source": source},
                ],
                "files": [
                    {
                        "id": "sp-file-1",
                        "name": "Organigramm.pdf",
                        "original_name": "Organigramm.pdf",
                        "size_bytes": 245_000,
                        "content_type": "application/pdf",
                        "web_url": "https://www.office.com",
                        "source": source,
                    }
                ],
                "mock": True,
            }
        return {
            "source": source,
            "current_item_id": "root",
            "parent_item_id": None,
            "breadcrumbs": [{"id": "root", "name": root_name}],
            "folders": [
                {"id": "od-documents", "name": "Dokumente", "source": source},
                {"id": "od-shared", "name": "Freigegeben", "source": source},
            ],
            "files": [
                {
                    "id": "od-file-1",
                    "name": "Notizen.docx",
                    "original_name": "Notizen.docx",
                    "size_bytes": 88_000,
                    "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "web_url": "https://www.office.com",
                    "source": source,
                }
            ],
            "mock": True,
        }

    children = _MOCK_CHILDREN.get(item_id or "", {"folders": [], "files": []})
    parent_id = _MOCK_PARENT.get(item_id or "", "root")
    breadcrumbs = [{"id": "root", "name": root_name}]
    if parent_id != "root" and parent_id in _MOCK_NAMES:
        breadcrumbs.append({"id": parent_id, "name": _MOCK_NAMES[parent_id]})
    breadcrumbs.append({"id": item_id, "name": _MOCK_NAMES.get(item_id or "", item_id or "")})
    return {
        "source": source,
        "current_item_id": item_id,
        "parent_item_id": parent_id,
        "breadcrumbs": breadcrumbs,
        "folders": children.get("folders", []),
        "files": children.get("files", []),
        "mock": True,
    }


def _parse_sharepoint_site_path(site_url: str) -> str:
    parsed = urlparse(site_url.strip())
    hostname = parsed.netloc
    path = parsed.path.strip("/")
    if not hostname or not path:
        raise HTTPException(status_code=400, detail="sharepoint_not_configured")
    return f"{hostname}:/{path}"


async def _graph_get_with_token(path: str, token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(
            f"{GRAPH_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code != 200:
            logger.error("Graph files request failed %s: %s", path, response.text)
            raise HTTPException(status_code=502, detail="graph_files_failed")
        return response.json()


async def _graph_get(path: str, settings: Settings | None = None) -> dict[str, Any]:
    token = await get_app_access_token(settings)
    return await _graph_get_with_token(path, token)


def _map_drive_item(item: dict[str, Any], source: str) -> dict[str, Any]:
    name = item.get("name") or "untitled"
    if "folder" in item:
        return {
            "id": item["id"],
            "name": name,
            "source": source,
            "child_count": item.get("folder", {}).get("childCount"),
        }
    file_info = item.get("file", {})
    return {
        "id": item["id"],
        "name": name,
        "original_name": name,
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


async def _browse_drive_with_token(
    *,
    token: str,
    source: str,
    root_name: str,
    root_children_path: str,
    item_children_path: str,
    item_path: str,
    item_id: str | None,
) -> dict:
    if not item_id or item_id == "root":
        path = root_children_path
        current_item_id = "root"
        parent_item_id = None
        breadcrumbs = [{"id": "root", "name": root_name}]
    else:
        path = item_children_path
        current = await _graph_get_with_token(item_path, token)
        current_item_id = item_id
        parent_item_id = current.get("parentReference", {}).get("id")
        breadcrumbs = [{"id": "root", "name": root_name}]
        if current.get("name"):
            breadcrumbs.append({"id": current_item_id, "name": current["name"]})

    payload = await _graph_get_with_token(path, token)
    folders, files = _split_drive_items(payload, source)
    return {
        "source": source,
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
    *,
    db: Session | None = None,
    user_id: str = "",
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()

    # Prefer per-user delegated token (Calendar-Tab / Outlook verbinden).
    if db is not None and user_id:
        try:
            delegated = await get_outlook_access_token(db, user_id=user_id)
        except HTTPException:
            delegated = None
        if delegated:
            return await _browse_drive_with_token(
                token=delegated,
                source="onedrive",
                root_name="Mein OneDrive",
                root_children_path="/me/drive/root/children",
                item_children_path=f"/me/drive/items/{item_id}/children",
                item_path=f"/me/drive/items/{item_id}",
                item_id=item_id,
            )

    if settings.files_browse_mock_mode or not settings.graph_publish_configured:
        return _mock_browse("onedrive", item_id)

    normalized_email = user_email.strip()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="validation")

    return await _browse_drive_with_token(
        token=await get_app_access_token(settings),
        source="onedrive",
        root_name="OneDrive",
        root_children_path=f"/users/{normalized_email}/drive/root/children",
        item_children_path=f"/users/{normalized_email}/drive/items/{item_id}/children",
        item_path=f"/users/{normalized_email}/drive/items/{item_id}",
        item_id=item_id,
    )
