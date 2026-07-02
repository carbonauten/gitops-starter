from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .config import get_settings


def save_upload(content: bytes, original_name: str) -> tuple[str, str, Path]:
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    destination = upload_root / stored_name
    destination.write_bytes(content)
    return stored_name, str(destination), destination


def delete_upload(storage_path: str) -> None:
    path = Path(storage_path)
    if path.exists():
        path.unlink()
