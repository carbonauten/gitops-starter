from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import Department, UserAccount, UserInvite
from .email_service import send_invite_email
from .roles import ALL_ROLES, ROLE_IT_MASTER
from .user_service import create_user_account, enrich_user_session, get_user_by_email

logger = logging.getLogger(__name__)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _invite_is_pending(invite: UserInvite, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return invite.accepted_at is None and _as_utc(invite.expires_at) > now


ROLE_LABELS = {
    "it_master": "IT-Master",
    "editor": "Redakteur",
    "viewer": "Leser",
}


def queue_invite_email(
    *,
    to_email: str,
    invite_url: str,
    role: str,
    invited_by_name: str,
) -> None:
    settings = get_settings()
    send_invite_email(
        to_email=to_email,
        invite_url=invite_url,
        role_label=ROLE_LABELS.get(role, role),
        invited_by_name=invited_by_name,
        expires_days=settings.invite_expiry_days,
    )


def invite_to_dict(invite: UserInvite, department: Department | None = None) -> dict:
    settings = get_settings()
    invite_url = f"{settings.invite_base_url}/invite/{invite.token}"
    now = datetime.now(timezone.utc)
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "department_id": invite.department_id,
        "department_name": department.name if department else None,
        "invited_by_name": invite.invited_by_name,
        "expires_at": invite.expires_at.isoformat(),
        "accepted_at": invite.accepted_at.isoformat() if invite.accepted_at else None,
        "created_at": invite.created_at.isoformat(),
        "status": "accepted"
        if invite.accepted_at
        else ("expired" if _as_utc(invite.expires_at) <= now else "pending"),
        "invite_url": invite_url,
    }


def list_invites(db: Session) -> list[dict]:
    invites = list(
        db.scalars(select(UserInvite).order_by(UserInvite.created_at.desc())).all()
    )
    department_ids = {invite.department_id for invite in invites if invite.department_id}
    departments: dict[str, Department] = {}
    if department_ids:
        departments = {
            department.id: department
            for department in db.scalars(select(Department).where(Department.id.in_(department_ids))).all()
        }
    return [invite_to_dict(invite, departments.get(invite.department_id)) for invite in invites]


def get_invite_by_token(db: Session, token: str) -> UserInvite:
    invite = db.scalar(select(UserInvite).where(UserInvite.token == token))
    if not invite:
        raise HTTPException(status_code=404, detail="invite_not_found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="invite_already_used")
    if _as_utc(invite.expires_at) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="invite_expired")
    return invite


def create_invite(
    db: Session,
    *,
    email: str,
    role: str,
    department_id: str | None,
    invited_by_id: str,
    invited_by_name: str,
) -> dict:
    settings = get_settings()
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=422, detail="validation")
    if role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    if role == ROLE_IT_MASTER and normalized_email not in settings.it_admin_emails_list:
        raise HTTPException(status_code=400, detail="it_role_locked")

    existing_user = get_user_by_email(db, normalized_email)
    if existing_user and existing_user.is_active:
        raise HTTPException(status_code=409, detail="user_exists")

    if department_id:
        department = db.get(Department, department_id)
        if not department or not department.is_active:
            raise HTTPException(status_code=404, detail="not_found")

    for pending in db.scalars(
        select(UserInvite).where(UserInvite.email == normalized_email, UserInvite.accepted_at.is_(None))
    ).all():
        db.delete(pending)

    now = datetime.now(timezone.utc)
    invite = UserInvite(
        email=normalized_email,
        role=role,
        department_id=department_id,
        token=secrets.token_urlsafe(32),
        invited_by_id=invited_by_id,
        invited_by_name=invited_by_name,
        expires_at=now + timedelta(days=settings.invite_expiry_days),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    department = db.get(Department, department_id) if department_id else None
    payload = invite_to_dict(invite, department)
    payload["email_pending"] = settings.smtp_configured
    payload["email_sent"] = False
    if not settings.smtp_configured:
        logger.warning(
            "SMTP not configured; invite link for %s: %s",
            normalized_email,
            payload["invite_url"],
        )
    return payload


def resend_invite(db: Session, invite_id: str) -> dict:
    invite = db.get(UserInvite, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="not_found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="invite_already_used")

    settings = get_settings()
    invite.token = secrets.token_urlsafe(32)
    invite.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.invite_expiry_days)
    db.commit()
    db.refresh(invite)

    department = db.get(Department, invite.department_id) if invite.department_id else None
    payload = invite_to_dict(invite, department)
    payload["email_pending"] = settings.smtp_configured
    payload["email_sent"] = False
    return payload


def revoke_invite(db: Session, invite_id: str) -> None:
    invite = db.get(UserInvite, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="not_found")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="invite_already_used")
    db.delete(invite)
    db.commit()


def accept_invite(db: Session, *, token: str, name: str, password: str) -> dict:
    invite = get_invite_by_token(db, token)
    normalized_name = name.strip()
    if not normalized_name or len(password) < 8:
        raise HTTPException(status_code=422, detail="validation")

    existing_user = get_user_by_email(db, invite.email)
    if existing_user and existing_user.is_active:
        raise HTTPException(status_code=409, detail="user_exists")

    user = create_user_account(
        db,
        email=invite.email,
        name=normalized_name,
        password=password,
        role=invite.role,
        department_id=invite.department_id,
    )
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return enrich_user_session(db, user)


def get_public_invite(db: Session, token: str) -> dict:
    invite = get_invite_by_token(db, token)
    department = db.get(Department, invite.department_id) if invite.department_id else None
    return {
        "email": invite.email,
        "role": invite.role,
        "department_name": department.name if department else None,
        "invited_by_name": invite.invited_by_name,
        "expires_at": invite.expires_at.isoformat(),
    }
