from __future__ import annotations

import mimetypes
from pathlib import Path


def _media_type(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix == ".js":
        return "application/javascript"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    return "application/octet-stream"


def resolve_asset_path(static_dir: Path, asset_name: str) -> Path | None:
    if not asset_name or "/" in asset_name or ".." in asset_name:
        return None
    path = static_dir / "assets" / asset_name
    if not path.is_file():
        return None
    return path


def resolve_root_file(static_dir: Path, filename: str) -> Path | None:
    if not filename or "/" in filename or ".." in filename:
        return None
    path = static_dir / filename
    if not path.is_file():
        return None
    return path


def media_type_for(path: Path) -> str:
    return _media_type(path)
