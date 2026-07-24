from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit_service import log_audit
from .certificates import compute_certificate_status, days_until_expiry
from .config import get_settings
from .database import Certificate, Publication, PublicationDelivery
from .email_service import send_plain_email

logger = logging.getLogger(__name__)

REMINDER_WINDOWS = (90, 60, 30)


def validate_parent_id(
    db: Session,
    *,
    certificate_id: Optional[str],
    parent_id: Optional[str],
) -> None:
    if not parent_id:
        return
    if certificate_id and parent_id == certificate_id:
        raise HTTPException(status_code=422, detail="invalid_parent")
    parent = db.get(Certificate, parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="not_found")

    # Prevent cycles: walk ancestors of the new parent.
    seen = {certificate_id} if certificate_id else set()
    current_id: Optional[str] = parent_id
    while current_id:
        if current_id in seen:
            raise HTTPException(status_code=422, detail="invalid_parent")
        seen.add(current_id)
        current = db.get(Certificate, current_id)
        if not current:
            break
        current_id = current.parent_id


def children_of(db: Session, certificate_id: str) -> list[Certificate]:
    return list(
        db.scalars(
            select(Certificate)
            .where(Certificate.parent_id == certificate_id)
            .order_by(Certificate.name.asc())
        ).all()
    )


def parent_name(db: Session, parent_id: Optional[str]) -> Optional[str]:
    if not parent_id:
        return None
    parent = db.get(Certificate, parent_id)
    return parent.name if parent else None


def chain_node(db: Session, certificate: Certificate, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    return {
        "id": certificate.id,
        "name": certificate.name,
        "category": certificate.category,
        "status": compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress, today),
        "valid_to": certificate.valid_to.isoformat(),
        "days_until_expiry": days_until_expiry(certificate.valid_to, today),
        "parent_id": certificate.parent_id,
        "children": [chain_node(db, child, today) for child in children_of(db, certificate.id)],
    }


def build_certificate_chains(db: Session, today: Optional[date] = None) -> list[dict[str, Any]]:
    today = today or date.today()
    roots = db.scalars(select(Certificate).where(Certificate.parent_id.is_(None)).order_by(Certificate.name.asc())).all()
    return [chain_node(db, root, today) for root in roots]


def due_reminder_windows(certificate: Certificate, today: Optional[date] = None) -> list[int]:
    today = today or date.today()
    days_left = days_until_expiry(certificate.valid_to, today)
    due: list[int] = []
    for window in REMINDER_WINDOWS:
        if days_left > window:
            continue
        sent_attr = f"reminder_{window}_sent_on"
        already = getattr(certificate, sent_attr, None)
        if already is None:
            due.append(window)
    return due


def mark_reminder_sent(certificate: Certificate, window: int, today: Optional[date] = None) -> None:
    today = today or date.today()
    setattr(certificate, f"reminder_{window}_sent_on", today)


def reminder_recipients(certificate: Certificate) -> list[str]:
    recipients: list[str] = []
    for email in (certificate.responsible_email, certificate.escalate_email):
        cleaned = (email or "").strip().lower()
        if cleaned and cleaned not in recipients:
            recipients.append(cleaned)
    return recipients


def build_reminder_message(certificate: Certificate, window: int) -> tuple[str, str]:
    days_left = days_until_expiry(certificate.valid_to)
    subject = f"[Carbonauten] Zertifikat läuft in ≤{window} Tagen ab: {certificate.name}"
    body = (
        f"Hallo {certificate.responsible_name or 'Team'},\n\n"
        f"das Zertifikat „{certificate.name}“ läuft bald ab.\n\n"
        f"Kategorie: {certificate.category}\n"
        f"Aussteller: {certificate.issuer or '—'}\n"
        f"Gültig bis: {certificate.valid_to.isoformat()}\n"
        f"Tage bis Ablauf: {days_left}\n"
        f"Erinnerungsfenster: {window} Tage\n"
        f"Verantwortlich: {certificate.responsible_name} ({certificate.responsible_email})\n"
    )
    if certificate.escalate_email:
        body += f"Eskalation: {certificate.escalate_email}\n"
    if certificate.parent_id:
        body += f"Parent-ID: {certificate.parent_id}\n"
    body += (
        "\nBitte Erneuerung starten oder Status in der Unified Carbonauten Platform aktualisieren.\n"
        f"\n— {get_settings().app_name}\n"
    )
    return subject, body


def build_audit_export_zip(db: Session, today: Optional[date] = None) -> bytes:
    today = today or date.today()
    certificates = list(db.scalars(select(Certificate).order_by(Certificate.valid_to.asc())).all())

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(
        [
            "id",
            "name",
            "category",
            "issuer",
            "valid_from",
            "valid_to",
            "status",
            "days_until_expiry",
            "parent_id",
            "parent_name",
            "responsible_name",
            "responsible_email",
            "escalate_email",
            "renewal_in_progress",
            "notes",
        ]
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(certificates),
        "valid": 0,
        "expiring": 0,
        "expired": 0,
        "renewal": 0,
        "with_parent": 0,
        "overdue": 0,
    }

    for certificate in certificates:
        status = compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress, today)
        days_left = days_until_expiry(certificate.valid_to, today)
        summary[status] = summary.get(status, 0) + 1
        if certificate.parent_id:
            summary["with_parent"] += 1
        if days_left < 0:
            summary["overdue"] += 1
        writer.writerow(
            [
                certificate.id,
                certificate.name,
                certificate.category,
                certificate.issuer,
                certificate.valid_from.isoformat(),
                certificate.valid_to.isoformat(),
                status,
                days_left,
                certificate.parent_id or "",
                parent_name(db, certificate.parent_id) or "",
                certificate.responsible_name,
                certificate.responsible_email,
                certificate.escalate_email,
                certificate.renewal_in_progress,
                certificate.notes,
            ]
        )

    chains = build_certificate_chains(db, today)
    report_lines = [
        "# Carbonauten Certificate Audit Pack",
        "",
        f"Generated: {summary['generated_at']}",
        f"Total certificates: {summary['total']}",
        f"Valid: {summary['valid']}",
        f"Expiring: {summary['expiring']}",
        f"Expired: {summary['expired']}",
        f"Renewal: {summary['renewal']}",
        f"With parent link: {summary['with_parent']}",
        f"Overdue: {summary['overdue']}",
        "",
        "## Files",
        "- certificates.csv — flat inventory with chain links",
        "- chains.json — parent/child trees",
        "- summary.json — counts for auditors",
    ]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("certificates.csv", csv_buffer.getvalue())
        archive.writestr("chains.json", json.dumps(chains, indent=2, ensure_ascii=False))
        archive.writestr("summary.json", json.dumps(summary, indent=2))
        archive.writestr("README.md", "\n".join(report_lines) + "\n")
    return zip_buffer.getvalue()


async def process_due_certificate_reminders(
    db: Session,
    *,
    actor: Optional[dict] = None,
    send_email: bool = True,
) -> dict[str, Any]:
    """Send once-per-window reminders for 90/60/30 day thresholds."""
    from .publish_service import _run_deliveries, ensure_publish_settings

    today = date.today()
    actor = actor or {
        "db_id": "system",
        "id": "system",
        "name": "System",
        "email": "",
    }
    settings_row = ensure_publish_settings(db)
    settings = get_settings()
    triggered: list[dict[str, Any]] = []

    certificates = list(db.scalars(select(Certificate)).all())
    for certificate in certificates:
        windows = due_reminder_windows(certificate, today)
        if not windows:
            continue

        for window in windows:
            subject, body = build_reminder_message(certificate, window)
            recipients = reminder_recipients(certificate)
            email_sent = 0
            if send_email and settings.email_delivery_configured:
                for recipient in recipients:
                    if send_plain_email(to_email=recipient, subject=subject, body=body, settings=settings):
                        email_sent += 1

            publication = Publication(
                resource_type="certificate_reminder",
                resource_id=certificate.id,
                title=subject,
                summary=body,
                published_by_id=actor.get("db_id") or actor.get("id") or "system",
                published_by_name=actor.get("name") or "System",
            )
            db.add(publication)
            db.flush()

            channels: list[str] = []
            if settings_row.teams_enabled:
                channels.append("teams")
            if settings_row.outlook_enabled:
                channels.append("outlook")
            if not channels and settings.publish_mock_mode:
                channels = ["teams", "outlook"]

            deliveries = [
                PublicationDelivery(publication_id=publication.id, channel=channel, status="pending")
                for channel in channels
            ]
            if deliveries:
                db.add_all(deliveries)
                db.flush()
                await _run_deliveries(
                    db,
                    deliveries,
                    title=subject,
                    body_html=f"<pre>{body}</pre>",
                    summary=body,
                    settings_row=settings_row,
                    to_email=certificate.responsible_email or None,
                )

            mark_reminder_sent(certificate, window, today)
            log_audit(
                db,
                entity_type="certificate",
                entity_id=certificate.id,
                action="reminder_sent",
                actor=actor,
                details={"window": window, "email_sent": email_sent, "recipients": recipients},
            )
            triggered.append(
                {
                    "certificate_id": certificate.id,
                    "certificate_name": certificate.name,
                    "window_days": window,
                    "days_until_expiry": days_until_expiry(certificate.valid_to, today),
                    "email_sent": email_sent,
                    "recipients": recipients,
                    "publication_id": publication.id,
                }
            )

    db.commit()
    return {"reminders_sent": len(triggered), "items": triggered}
