from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import get_settings

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@lru_cache
def _load_locale(language: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_language(language: str | None) -> str:
    settings = get_settings()
    if not language:
        return settings.default_language

    normalized = language.strip()
    if normalized in settings.supported_languages:
        return normalized

    primary = normalized.split(",")[0].split(";")[0].strip()
    if primary in settings.supported_languages:
        return primary

    short = primary.split("-")[0]
    if short == "zh":
        return "zh-CN"

    for supported in settings.supported_languages:
        if supported.startswith(short):
            return supported

    return settings.default_language


def parse_accept_language(header: str | None) -> str:
    if not header:
        return get_settings().default_language

    parts = []
    for item in header.split(","):
        chunk = item.strip()
        if not chunk:
            continue
        lang = chunk.split(";")[0].strip()
        parts.append(lang)

    for lang in parts:
        resolved = normalize_language(lang)
        if resolved in get_settings().supported_languages:
            return resolved

    return get_settings().default_language


def translate(key: str, language: str | None = None, **kwargs: str) -> str:
    lang = normalize_language(language)
    catalog = _load_locale(lang)
    fallback = _load_locale(get_settings().default_language)
    message = catalog.get(key) or fallback.get(key) or key
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
    return message
