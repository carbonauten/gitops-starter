from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

import httpx

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


def _invite_subject(settings: Settings) -> str:
    return f"Einladung zur {settings.app_name}"


def _invite_body(
    *,
    invited_by_name: str,
    settings: Settings,
    role_label: str,
    invite_url: str,
    expires_days: int,
) -> str:
    return (
        f"Hallo,\n\n"
        f"{invited_by_name} hat Sie zur {settings.app_name} eingeladen.\n\n"
        f"Rolle: {role_label}\n"
        f"Link (gültig {expires_days} Tage):\n{invite_url}\n\n"
        f"Falls der Link nicht funktioniert, kopieren Sie die URL in Ihren Browser.\n"
    )


def _from_header(settings: Settings) -> str:
    from_name = settings.smtp_from_name.strip() or settings.app_name
    return f"{from_name} <{settings.effective_from_email}>"


def _send_via_resend(
    settings: Settings,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key.strip()}",
                "Content-Type": "application/json",
            },
            json={
                "from": _from_header(settings),
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Resend failed to send invite email to %s", to_email)
        return False


def _send_via_smtp(
    settings: Settings,
    *,
    to_email: str,
    subject: str,
    body: str,
) -> bool:
    message = EmailMessage()
    message["From"] = _from_header(settings)
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("SMTP failed to send invite email to %s", to_email)
        return False


def send_invite_email(
    *,
    to_email: str,
    invite_url: str,
    role_label: str,
    invited_by_name: str,
    expires_days: int,
    settings: Settings | None = None,
) -> bool:
    settings = settings or get_settings()
    subject = _invite_subject(settings)
    body = _invite_body(
        invited_by_name=invited_by_name,
        settings=settings,
        role_label=role_label,
        invite_url=invite_url,
        expires_days=expires_days,
    )

    if settings.resend_configured:
        return _send_via_resend(settings, to_email=to_email, subject=subject, body=body)

    if settings.smtp_configured:
        logger.warning(
            "Using SMTP for invite to %s. Railway Hobby blocks SMTP — set RESEND_API_KEY instead.",
            to_email,
        )
        return _send_via_smtp(settings, to_email=to_email, subject=subject, body=body)

    logger.warning("Email not configured; invite link for %s: %s", to_email, invite_url)
    return False
