from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .database import FileAsset
from .embedding_service import queue_reembed
from .file_folder_service import folder_path, resolve_upload_folder
from .graph_files_service import download_sharepoint_item
from .storage import save_upload


def guess_certificate_name(filename: str) -> str:
    stem = Path(filename).stem.strip().replace("_", " ").replace("-", " ")
    return stem or filename or "SharePoint Import"


def guess_certificate_category(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith((".crt", ".cer", ".pem", ".key")):
        return "ssl"
    if "schulung" in lower or "training" in lower or "erste-hilfe" in lower:
        return "training"
    if "produkt" in lower or "product" in lower or "reach" in lower or " ce " in f" {lower} ":
        return "product"
    return "compliance"


async def import_sharepoint_item_as_file_asset(
    db: Session,
    *,
    item_id: str,
    user: dict[str, Any],
    folder: str = "certificates",
    background_tasks: Optional[BackgroundTasks] = None,
) -> tuple[FileAsset, dict[str, Any]]:
    settings = get_settings()
    downloaded = await download_sharepoint_item(item_id, settings)
    content = downloaded["content"]
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="file_too_large")

    original_name = Path(downloaded["original_name"] or downloaded["name"] or "sharepoint-file.bin").name
    stored_name, storage_path, _ = save_upload(content, original_name)
    target_folder = resolve_upload_folder(db, folder_id=None, folder_slug=folder)

    file_asset = FileAsset(
        original_name=original_name,
        stored_name=stored_name,
        content_type=downloaded.get("content_type") or "application/octet-stream",
        size_bytes=len(content),
        folder=folder_path(target_folder),
        folder_id=target_folder.id,
        storage_path=storage_path,
        uploaded_by_id=user["id"],
        uploaded_by_name=user["name"],
    )
    db.add(file_asset)
    db.commit()
    db.refresh(file_asset)
    if background_tasks is not None:
        queue_reembed(background_tasks, entity_type="file", entity_id=file_asset.id)
    return file_asset, downloaded
