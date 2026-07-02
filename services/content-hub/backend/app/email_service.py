from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


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
    if not settings.smtp_configured:
        logger.warning("SMTP not configured; invite link for %s: %s", to_email, invite_url)
        return False

    subject = f"Einladung zur {settings.app_name}"
    body = (
        f"Hallo,\n\n"
        f"{invited_by_name} hat Sie zur {settings.app_name} eingeladen.\n\n"
        f"Rolle: {role_label}\n"
        f"Link (gültig {expires_days} Tage):\n{invite_url}\n\n"
        f"Falls der Link nicht funktioniert, kopieren Sie die URL in Ihren Browser.\n"
    )

    message = EmailMessage()
    from_name = settings.smtp_from_name.strip() or settings.app_name
    message["From"] = f"{from_name} <{settings.smtp_from_email.strip()}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send invite email to %s", to_email)
        return False
