from __future__ import annotations

from pathlib import Path

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..auth import require_user
from ..config import get_settings
from ..database import FileAsset, get_db
from ..schemas import FileResponse as FileSchema
from ..storage import delete_upload, save_upload

router = APIRouter(prefix="/api/files", tags=["files"])


def _to_response(file_asset: FileAsset) -> FileSchema:
    return FileSchema(
        id=file_asset.id,
        original_name=file_asset.original_name,
        content_type=file_asset.content_type,
        size_bytes=file_asset.size_bytes,
        folder=file_asset.folder,
        uploaded_by_id=file_asset.uploaded_by_id,
        uploaded_by_name=file_asset.uploaded_by_name,
        created_at=file_asset.created_at,
    )


@router.get("")
def list_files(
    q: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_user),
) -> dict:
    stmt = select(FileAsset).order_by(FileAsset.created_at.desc())
    if folder:
        stmt = stmt.where(FileAsset.folder == folder)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(FileAsset.original_name.ilike(pattern), FileAsset.folder.ilike(pattern)))
    files = db.scalars(stmt).all()
    folders = sorted(db.scalars(select(FileAsset.folder).distinct()).all())
    return {
        "files": [_to_response(item) for item in files],
        "folders": folders,
    }


@router.post("/upload", status_code=201)
async def upload_file(
    upload: UploadFile = File(...),
    folder: str = Form(default="general"),
    db: Session = Depends(get_db),
    user: dict = Depends(require_user),
) -> dict:
    settings = get_settings()
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail="file_too_large")

    original_name = Path(upload.filename or "upload.bin").name
    stored_name, storage_path, _ = save_upload(content, original_name)

    file_asset = FileAsset(
        original_name=original_name,
        stored_name=stored_name,
        content_type=upload.content_type or "application/octet-stream",
        size_bytes=len(content),
        folder=folder.strip() or "general",
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
    _user: dict = Depends(require_user),
) -> dict:
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    return {"file": _to_response(file_asset)}


@router.get("/{file_id}/download")
def download_file(
    file_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_user),
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
    _user: dict = Depends(require_user),
):
    file_asset = db.get(FileAsset, file_id)
    if not file_asset:
        raise HTTPException(status_code=404, detail="not_found")
    delete_upload(file_asset.storage_path)
    db.delete(file_asset)
    db.commit()
    return Response(status_code=204)
