from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import UserAccount
from .i18n import normalize_language
from .roles import ALL_ROLES, ROLE_EDITOR, ROLE_IT_MASTER


def resolve_role_for_email(email: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if email.strip().lower() in settings.it_admin_emails_list:
        return ROLE_IT_MASTER
    default_role = settings.default_user_role
    if default_role not in ALL_ROLES or default_role == ROLE_IT_MASTER:
        return ROLE_EDITOR
    return default_role


def user_to_session(user: UserAccount) -> dict:
    return {
        "id": user.entra_id,
        "db_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "language": user.language,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def upsert_user_from_login(
    db: Session,
    *,
    entra_id: str,
    email: str,
    name: str,
    language: str | None = None,
) -> UserAccount:
    settings = get_settings()
    normalized_email = email.strip().lower()
    language = normalize_language(language or settings.default_language)
    now = datetime.now(timezone.utc)

    user = db.scalar(select(UserAccount).where(UserAccount.entra_id == entra_id))
    if user is None:
        if not settings.allow_self_registration and not settings.entra_mock_auth:
            raise HTTPException(status_code=403, detail="registration_disabled")
        user = UserAccount(
            entra_id=entra_id,
            email=normalized_email,
            name=name,
            role=resolve_role_for_email(normalized_email, settings),
            language=language,
            is_active=True,
            last_login_at=now,
        )
        db.add(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=403, detail="account_disabled")
        user.email = normalized_email
        user.name = name
        user.last_login_at = now
        if language:
            user.language = language
        if normalized_email in settings.it_admin_emails_list:
            user.role = ROLE_IT_MASTER

    db.commit()
    db.refresh(user)
    return user


def get_user_by_entra_id(db: Session, entra_id: str) -> UserAccount | None:
    return db.scalar(select(UserAccount).where(UserAccount.entra_id == entra_id))


def list_users(db: Session) -> list[UserAccount]:
    return list(db.scalars(select(UserAccount).order_by(UserAccount.name.asc())).all())


def update_user_role(db: Session, user_id: str, role: str) -> UserAccount:
    if role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    if role != ROLE_IT_MASTER and user.email.lower() in get_settings().it_admin_emails_list:
        raise HTTPException(status_code=400, detail="it_role_locked")
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def update_user_active(db: Session, user_id: str, is_active: bool) -> UserAccount:
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    if not is_active and user.email.lower() in get_settings().it_admin_emails_list:
        raise HTTPException(status_code=400, detail="it_account_locked")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
