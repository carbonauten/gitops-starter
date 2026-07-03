from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from .config import get_settings

logger = logging.getLogger(__name__)


def _object_key(stored_name: str) -> str:
    settings = get_settings()
    prefix = settings.oss_object_prefix.strip().strip("/")
    if prefix:
        return f"{prefix}/{stored_name}"
    return stored_name


def save_upload_local(content: bytes, original_name: str) -> tuple[str, str, Path]:
    settings = get_settings()
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    destination = upload_root / stored_name
    destination.write_bytes(content)
    return stored_name, str(destination), destination


def save_upload_oss(content: bytes, original_name: str) -> tuple[str, str, Path]:
    settings = get_settings()
    if not settings.oss_configured:
        raise HTTPException(status_code=500, detail="oss_not_configured")

    try:
        import oss2
    except ImportError as exc:  # pragma: no cover - dependency optional in dev
        raise HTTPException(status_code=500, detail="oss_not_configured") from exc

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid4().hex}{suffix}"
    key = _object_key(stored_name)
    auth = oss2.Auth(settings.oss_access_key_id.strip(), settings.oss_access_key_secret.strip())
    bucket = oss2.Bucket(auth, settings.oss_endpoint.strip(), settings.oss_bucket.strip())
    bucket.put_object(key, content)
    storage_path = f"oss://{settings.oss_bucket.strip()}/{key}"
    return stored_name, storage_path, Path(storage_path)


def save_upload(content: bytes, original_name: str) -> tuple[str, str, Path]:
    settings = get_settings()
    if settings.storage_backend == "oss":
        return save_upload_oss(content, original_name)
    return save_upload_local(content, original_name)


def read_upload(storage_path: str) -> bytes:
    if storage_path.startswith("oss://"):
        settings = get_settings()
        if not settings.oss_configured:
            raise HTTPException(status_code=500, detail="oss_not_configured")
        try:
            import oss2
        except ImportError as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="oss_not_configured") from exc

        _, remainder = storage_path.split("oss://", 1)
        bucket_name, key = remainder.split("/", 1)
        auth = oss2.Auth(settings.oss_access_key_id.strip(), settings.oss_access_key_secret.strip())
        bucket = oss2.Bucket(auth, settings.oss_endpoint.strip(), bucket_name)
        result = bucket.get_object(key)
        return result.read()

    path = Path(storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="not_found")
    return path.read_bytes()


def delete_upload(storage_path: str) -> None:
    if storage_path.startswith("oss://"):
        settings = get_settings()
        if not settings.oss_configured:
            return
        try:
            import oss2
        except ImportError:
            return
        _, remainder = storage_path.split("oss://", 1)
        bucket_name, key = remainder.split("/", 1)
        auth = oss2.Auth(settings.oss_access_key_id.strip(), settings.oss_access_key_secret.strip())
        bucket = oss2.Bucket(auth, settings.oss_endpoint.strip(), bucket_name)
        bucket.delete_object(key)
        return

    path = Path(storage_path)
    if path.exists():
        path.unlink()


def open_upload_stream(storage_path: str) -> BytesIO:
    return BytesIO(read_upload(storage_path))
