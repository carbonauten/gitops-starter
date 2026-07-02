from fastapi import APIRouter

from ..config import get_settings

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "content-hub",
        "display_name": settings.app_name,
        "entra_configured": settings.entra_configured,
        "mock_auth": settings.entra_mock_auth,
        "supported_languages": list(settings.supported_languages),
    }


@router.get("/api/i18n/{language}")
def i18n_bundle(language: str) -> dict:
    from ..i18n import normalize_language, _load_locale

    lang = normalize_language(language)
    return {
        "language": lang,
        "messages": _load_locale(lang),
    }
