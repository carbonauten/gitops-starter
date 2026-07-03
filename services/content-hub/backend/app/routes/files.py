from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import FileAsset, get_db
from ..dependencies import get_current_user, require_editor
from ..file_folder_service import (
    build_folder_tree,
    create_folder,
    folder_path,
    get_folder,
    resolve_upload_folder,
)
from ..graph_files_service import browse_onedrive, browse_sharepoint
from ..schemas import FileResponse as FileSchema
from ..storage import delete_upload, save_upload

router = APIRouter(prefix="/api/files", tags=["files"])


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None


def _to_response(file_asset: FileAsset) -> FileSchema:
    return FileSchema(
        id=file_asset.id,
        original_name=file_asset.original_name,
        content_type=file_asset.content_type,
        size_bytes=file_asset.size_bytes,
        folder=file_asset.folder,
        folder_id=file_asset.folder_id,
        uploaded_by_id=file_asset.uploaded_by_id,
        uploaded_by_name=file_asset.uploaded_by_name,
        created_at=file_asset.created_at,
    )


def _platform_browse(db: Session, *, folder_id: str | None, q: str | None) -> dict:
    current_folder = None
    if folder_id:
        current_folder = get_folder(db, folder_id)

    stmt = select(FileAsset).order_by(FileAsset.created_at.desc())
    if folder_id:
        stmt = stmt.where(FileAsset.folder_id == folder_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(FileAsset.original_name.ilike(pattern), FileAsset.folder.ilike(pattern)))

    files = db.scalars(stmt).all()
    tree = build_folder_tree(db)

    def find_children(nodes: list[dict], target_id: str | None) -> list[dict]:
        if not target_id:
            return nodes
        for node in nodes:
            if node["id"] == target_id:
                return node.get("children", [])
            child_result = find_children(node.get("children", []), target_id)
            if child_result:
                return child_result
        return []

    folders = find_children(tree, folder_id) if folder_id else tree
    breadcrumbs = [{"id": "root", "name": "Plattform"}]
    if current_folder:
        breadcrumbs.append({"id": current_folder.id, "name": current_folder.name})

    return {
        "source": "platform",
        "current_item_id": folder_id or "root",
        "parent_item_id": current_folder.parent_id if current_folder else None,
        "breadcrumbs": breadcrumbs,
        "folders": [
            {
                "id": folder["id"],
                "name": folder["name"],
                "source": "platform",
                "path": folder["path"],
            }
            for folder in folders
        ],
        "files": [_to_response(file_asset).model_dump() for file_asset in files],
        "folder_tree": tree,
        "mock": False,
    }


@router.get("/sources")
def list_sources(_user: dict = Depends(get_current_user)) -> dict:
    settings = get_settings()
    return {
        "sources": [
            {
                "id": "platform",
                "label": "platform",
                "configured": True,
                "mock": False,
            },
            {
                "id": "sharepoint",
                "label": "sharepoint",
                "configured": settings.sharepoint_configured,
                "mock": settings.files_browse_mock_mode or not settings.sharepoint_configured,
            },
            {
                "id": "onedrive",
                "label": "onedrive",
                "configured": settings.graph_publish_configured,
                "mock": settings.files_browse_mock_mode or not settings.graph_publish_configured,
            },
        ]
    }


@router.get("/folders/tree")
def folder_tree(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"folders": build_folder_tree(db)}


@router.post("/folders", status_code=201)
def create_folder_route(
    payload: FolderCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
) -> dict:
    folder = create_folder(
        db,
        name=payload.name,
        slug=payload.slug,
        parent_id=payload.parent_id,
    )
    return {"folder": folder}


@router.get("/browse")
async def browse_files(
    source: Literal["platform", "sharepoint", "onedrive"] = Query(default="platform"),
    item_id: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    if source == "platform":
        folder_id = None if not item_id or item_id == "root" else item_id
        return _platform_browse(db, folder_id=folder_id, q=q)
    if source == "sharepoint":
        return await browse_sharepoint(item_id)
    return await browse_onedrive(user.get("email", ""), item_id)


@router.get("")
def list_files(
    q: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    folder_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    browse = _platform_browse(db, folder_id=folder_id, q=q)
    if folder and not folder_id:
        browse["files"] = [
            file
            for file in browse["files"]
            if file.get("folder") == folder
        ]
    return {
        "files": browse["files"],
        "folders": sorted(db.scalars(select(FileAsset.folder).distinct()).all()),
        "folder_tree": browse.get("folder_tree", []),
    }


@router.post("/upload", status_code=201)
async def upload_file(
    upload: UploadFile = File(...),
    folder: str = Form(default="general"),
    folder_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    settings = get_settings()
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="file_too_large")

    target_folder = resolve_upload_folder(db, folder_id=folder_id, folder_slug=folder)
    original_name = Path(upload.filename or "upload.bin").name
    stored_name, storage_path, _ = save_upload(content, original_name)

    file_asset = FileAsset(
        original_name=original_name,
        stored_name=stored_name,
        content_type=upload.content_type or "application/octet-stream",
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
    return {"file": _to_response(file_asset)}


@router.get("/{file_id}")
def get_file_metadata(
    file_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    return {"file": _to_response(file_asset)}


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    path = Path(file_asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(
        path,
        media_type=file_asset.content_type,
        filename=file_asset.original_name,
    )


@router.delete("/{file_id}", status_code=204)
def delete_file(
    file_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
):
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    delete_upload(file_asset.storage_path)
    db.delete(file_asset)
    db.commit()
    return Response(status_code=204)
