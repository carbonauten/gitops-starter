from __future__ import annotations

import mimetypes
from pathlib import Path

_ASSET_CACHE: dict[str, tuple[bytes, str]] = {}
_ROOT_FILE_CACHE: dict[str, tuple[bytes, str]] = {}
_INDEX_HTML: tuple[bytes, str] | None = None


def _media_type(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix == ".js":
        return "application/javascript"
    if path.suffix == ".css":
        return "text/css; charset=utf-8"
    return "application/octet-stream"


def preload_static(static_dir: Path) -> None:
    global _INDEX_HTML

    _ASSET_CACHE.clear()
    _ROOT_FILE_CACHE.clear()
    _INDEX_HTML = None

    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        for path in sorted(assets_dir.iterdir()):
            if path.is_file():
                _ASSET_CACHE[path.name] = (path.read_bytes(), _media_type(path))

    index = static_dir / "index.html"
    if index.is_file():
        _INDEX_HTML = (index.read_bytes(), "text/html; charset=utf-8")

    for path in sorted(static_dir.iterdir()):
        if path.is_file() and path.name != "index.html":
            _ROOT_FILE_CACHE[path.name] = (path.read_bytes(), _media_type(path))


def get_asset(asset_name: str) -> tuple[bytes, str] | None:
    return _ASSET_CACHE.get(asset_name)


def get_root_file(filename: str) -> tuple[bytes, str] | None:
    return _ROOT_FILE_CACHE.get(filename)


def get_index_html() -> tuple[bytes, str] | None:
    return _INDEX_HTML
