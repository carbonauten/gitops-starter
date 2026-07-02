from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Department, UserAccount

_CODE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,48}[a-z0-9])?$")


def normalize_department_code(code: str) -> str:
    return code.strip().lower().replace("_", "-")


def department_to_dict(department: Department, *, member_count: int | None = None) -> dict:
    payload = {
        "id": department.id,
        "name": department.name,
        "code": department.code,
        "is_active": department.is_active,
        "sort_order": department.sort_order,
    }
    if member_count is not None:
        payload["member_count"] = member_count
    return payload


def list_departments(db: Session, *, include_inactive: bool = False) -> list[dict]:
    query = select(Department).order_by(Department.sort_order.asc(), Department.name.asc())
    if not include_inactive:
        query = query.where(Department.is_active.is_(True))
    departments = list(db.scalars(query).all())
    counts = dict(
        db.execute(
            select(UserAccount.department_id, func.count())
            .where(UserAccount.department_id.is_not(None))
            .group_by(UserAccount.department_id)
        ).all()
    )
    return [department_to_dict(dept, member_count=counts.get(dept.id, 0)) for dept in departments]


def get_department(db: Session, department_id: str) -> Department:
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=404, detail="not_found")
    return department


def create_department(db: Session, *, name: str, code: str, sort_order: int = 0) -> Department:
    normalized_name = name.strip()
    normalized_code = normalize_department_code(code)
    if not normalized_name:
        raise HTTPException(status_code=422, detail="validation")
    if not _CODE_PATTERN.match(normalized_code):
        raise HTTPException(status_code=422, detail="validation")
    if db.scalar(select(Department).where(Department.code == normalized_code)):
        raise HTTPException(status_code=409, detail="department_exists")

    department = Department(
        name=normalized_name,
        code=normalized_code,
        sort_order=sort_order,
        is_active=True,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def update_department(
    db: Session,
    department_id: str,
    *,
    name: str | None = None,
    code: str | None = None,
    is_active: bool | None = None,
    sort_order: int | None = None,
) -> Department:
    department = get_department(db, department_id)
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise HTTPException(status_code=422, detail="validation")
        department.name = normalized_name
    if code is not None:
        normalized_code = normalize_department_code(code)
        if not _CODE_PATTERN.match(normalized_code):
            raise HTTPException(status_code=422, detail="validation")
        existing = db.scalar(
            select(Department).where(Department.code == normalized_code, Department.id != department_id)
        )
        if existing:
            raise HTTPException(status_code=409, detail="department_exists")
        department.code = normalized_code
    if is_active is not None:
        department.is_active = is_active
    if sort_order is not None:
        department.sort_order = sort_order
    db.commit()
    db.refresh(department)
    return department


def delete_department(db: Session, department_id: str) -> None:
    department = get_department(db, department_id)
    for user in db.scalars(select(UserAccount).where(UserAccount.department_id == department_id)).all():
        user.department_id = None
    db.delete(department)
    db.commit()
