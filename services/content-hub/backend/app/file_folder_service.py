from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import FileAsset, FileFolder

DEFAULT_FOLDERS: tuple[tuple[str, str], ...] = (
    ("general", "Allgemein"),
    ("compliance", "Compliance"),
    ("marketing", "Marketing"),
)


def seed_default_folders(db: Session) -> None:
    existing = db.scalar(select(FileFolder).limit(1))
    if existing:
        return
    for index, (slug, name) in enumerate(DEFAULT_FOLDERS):
        db.add(FileFolder(slug=slug, name=name, parent_id=None, sort_order=index * 10))
    db.commit()


def _folder_to_dict(folder: FileFolder, children: list[dict] | None = None) -> dict:
    return {
        "id": folder.id,
        "name": folder.name,
        "slug": folder.slug,
        "parent_id": folder.parent_id,
        "path": folder_path(folder),
        "children": children or [],
    }


def folder_path(folder: FileFolder, cache: dict[str, FileFolder] | None = None) -> str:
    if not folder.parent_id:
        return folder.slug
    if cache and folder.parent_id in cache:
        parent = cache[folder.parent_id]
        return f"{folder_path(parent, cache)}/{folder.slug}"
    return folder.slug


def build_folder_tree(db: Session) -> list[dict]:
    folders = list(db.scalars(select(FileFolder).order_by(FileFolder.sort_order, FileFolder.name)).all())
    if not folders:
        seed_default_folders(db)
        folders = list(db.scalars(select(FileFolder).order_by(FileFolder.sort_order, FileFolder.name)).all())

    by_parent: dict[str | None, list[FileFolder]] = {}
    cache = {folder.id: folder for folder in folders}
    for folder in folders:
        by_parent.setdefault(folder.parent_id, []).append(folder)

    def walk(parent_id: str | None) -> list[dict]:
        nodes = []
        for folder in by_parent.get(parent_id, []):
            nodes.append(_folder_to_dict(folder, walk(folder.id)))
        return nodes

    return walk(None)


def get_folder(db: Session, folder_id: str) -> FileFolder:
    folder = db.get(FileFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="not_found")
    return folder


def get_folder_by_slug_path(db: Session, slug_path: str) -> FileFolder | None:
    parts = [part for part in slug_path.strip("/").split("/") if part]
    if not parts:
        return None

    parent_id = None
    folder: FileFolder | None = None
    for part in parts:
        folder = db.scalar(
            select(FileFolder).where(FileFolder.slug == part, FileFolder.parent_id == parent_id)
        )
        if not folder:
            return None
        parent_id = folder.id
    return folder


def resolve_upload_folder(db: Session, *, folder_id: str | None, folder_slug: str | None) -> FileFolder:
    if folder_id:
        return get_folder(db, folder_id)
    if folder_slug:
        folder = get_folder_by_slug_path(db, folder_slug)
        if folder:
            return folder
    default = db.scalar(select(FileFolder).where(FileFolder.slug == "general", FileFolder.parent_id.is_(None)))
    if default:
        return default
    seed_default_folders(db)
    return db.scalar(select(FileFolder).where(FileFolder.slug == "general", FileFolder.parent_id.is_(None)))


def create_folder(db: Session, *, name: str, slug: str, parent_id: str | None) -> dict:
    slug = slug.strip().lower().replace(" ", "-")
    if not slug:
        raise HTTPException(status_code=422, detail="validation")
    if parent_id:
        get_folder(db, parent_id)
    exists = db.scalar(
        select(FileFolder).where(FileFolder.slug == slug, FileFolder.parent_id == parent_id)
    )
    if exists:
        raise HTTPException(status_code=409, detail="folder_exists")
    folder = FileFolder(name=name.strip(), slug=slug, parent_id=parent_id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return _folder_to_dict(folder)


def migrate_legacy_file_folders(db: Session) -> None:
    seed_default_folders(db)
    folders = list(db.scalars(select(FileFolder)).all())
    slug_map = {(folder.parent_id, folder.slug): folder for folder in folders}
    top_level = {folder.slug: folder for folder in folders if folder.parent_id is None}

    for file_asset in db.scalars(select(FileAsset).where(FileAsset.folder_id.is_(None))).all():
        legacy = (file_asset.folder or "general").strip() or "general"
        folder = top_level.get(legacy)
        if not folder:
            folder = top_level.get("general")
        if folder:
            file_asset.folder_id = folder.id
            file_asset.folder = folder_path(folder, {f.id: f for f in folders})
    db.commit()
