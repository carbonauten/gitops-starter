from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import Department, UserAccount
from .i18n import normalize_language
from .password_service import hash_password, verify_password
from .roles import ALL_ROLES, ROLE_EDITOR, ROLE_IT_MASTER


def sync_master_role_from_env(db: Session, user: UserAccount) -> UserAccount:
    settings = get_settings()
    if user.email.lower() in settings.it_admin_emails_list and user.role != ROLE_IT_MASTER:
        user.role = ROLE_IT_MASTER
        db.commit()
        db.refresh(user)
    return user


def resolve_role_for_email(email: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if email.strip().lower() in settings.it_admin_emails_list:
        return ROLE_IT_MASTER
    default_role = settings.default_user_role
    if default_role not in ALL_ROLES or default_role == ROLE_IT_MASTER:
        return ROLE_EDITOR
    return default_role


def user_to_session(user: UserAccount, department: Department | None = None) -> dict:
    return {
        "id": user.entra_id,
        "db_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "department_id": user.department_id,
        "department_name": department.name if department else None,
        "language": user.language,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


def enrich_user_session(db: Session, user: UserAccount) -> dict:
    department = db.get(Department, user.department_id) if user.department_id else None
    return user_to_session(user, department)


def users_to_sessions(db: Session, users: list[UserAccount]) -> list[dict]:
    department_ids = {user.department_id for user in users if user.department_id}
    departments: dict[str, Department] = {}
    if department_ids:
        departments = {
            department.id: department
            for department in db.scalars(select(Department).where(Department.id.in_(department_ids))).all()
        }
    return [user_to_session(user, departments.get(user.department_id)) for user in users]


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
        sync_master_role_from_env(db, user)

    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> UserAccount | None:
    return db.scalar(select(UserAccount).where(UserAccount.email == email.strip().lower()))


def authenticate_by_password(db: Session, email: str, password: str) -> UserAccount:
    normalized_email = email.strip().lower()
    user = get_user_by_email(db, normalized_email)
    if not user or not user.is_active or not user.password_hash:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    user.last_login_at = datetime.now(timezone.utc)
    sync_master_role_from_env(db, user)
    db.commit()
    db.refresh(user)
    return user


def ensure_initial_admin(db: Session) -> None:
    settings = get_settings()
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password.strip()
    if not email or not password:
        return

    user = get_user_by_email(db, email)
    password_hash = hash_password(password)
    display_name = settings.initial_admin_name.strip() or email.split("@", 1)[0].replace(".", " ").title()

    if user is None:
        user = UserAccount(
            entra_id=f"local-{uuid4()}",
            email=email,
            name=display_name,
            role=resolve_role_for_email(email, settings),
            password_hash=password_hash,
            language=settings.default_language,
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
    elif not user.password_hash:
        user.password_hash = password_hash
        user.name = display_name or user.name
        sync_master_role_from_env(db, user)

    db.commit()


def create_user_account(
    db: Session,
    *,
    email: str,
    name: str,
    password: str,
    role: str,
    department_id: str | None = None,
) -> UserAccount:
    if role not in ALL_ROLES:
        raise HTTPException(status_code=422, detail="validation")

    normalized_email = email.strip().lower()
    normalized_name = name.strip()
    if not normalized_email or not normalized_name or len(password) < 8:
        raise HTTPException(status_code=422, detail="validation")
    if get_user_by_email(db, normalized_email):
        raise HTTPException(status_code=409, detail="user_exists")

    if department_id:
        department = db.get(Department, department_id)
        if not department or not department.is_active:
            raise HTTPException(status_code=404, detail="not_found")

    user = UserAccount(
        entra_id=f"local-{uuid4()}",
        email=normalized_email,
        name=normalized_name,
        role=role if normalized_email not in get_settings().it_admin_emails_list else ROLE_IT_MASTER,
        department_id=department_id,
        password_hash=hash_password(password),
        language=get_settings().default_language,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_password(db: Session, user_id: str, password: str) -> UserAccount:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="validation")
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    user.password_hash = hash_password(password)
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


def update_user_department(db: Session, user_id: str, department_id: str | None) -> UserAccount:
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="not_found")
    if department_id:
        department = db.get(Department, department_id)
        if not department or not department.is_active:
            raise HTTPException(status_code=404, detail="not_found")
    user.department_id = department_id
    db.commit()
    db.refresh(user)
    return user
