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
        "password_auth": True,
        "microsoft_auth": settings.entra_configured and not settings.entra_mock_auth,
        "it_admin_configured": bool(settings.it_admin_emails_list),
        "bootstrap_admin_configured": bool(
            settings.initial_admin_email.strip() and settings.initial_admin_password.strip()
        ),
        "smtp_configured": settings.smtp_configured,
        "resend_configured": settings.resend_configured,
        "email_delivery_configured": settings.email_delivery_configured,
        "email_provider": settings.email_provider,
        "publish_mock_mode": settings.publish_mock_mode,
        "graph_publish_configured": settings.graph_publish_configured,
        "notion_configured": settings.notion_configured,
        "sharepoint_configured": settings.sharepoint_configured,
        "files_browse_mock_mode": settings.files_browse_mock_mode,
        "sso_redirect_uri": settings.effective_redirect_uri if settings.entra_configured else None,
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
