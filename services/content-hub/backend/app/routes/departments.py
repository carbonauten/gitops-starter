from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..department_service import (
    create_department,
    delete_department,
    department_to_dict,
    list_departments,
    update_department,
)
from ..dependencies import get_current_user, require_it_master

router = APIRouter(prefix="/api/departments", tags=["departments"])


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(..., min_length=1, max_length=50)
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


@router.get("")
def get_departments(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    departments = list_departments(db, include_inactive=include_inactive)
    return {"departments": departments}


@router.post("")
def post_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    department = create_department(
        db,
        name=payload.name,
        code=payload.code,
        sort_order=payload.sort_order,
    )
    return {"department": department_to_dict(department, member_count=0)}


@router.patch("/{department_id}")
def patch_department(
    department_id: str,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    department = update_department(
        db,
        department_id,
        name=payload.name,
        code=payload.code,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
    )
    return {"department": department_to_dict(department)}


@router.delete("/{department_id}")
def remove_department(
    department_id: str,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    delete_department(db, department_id)
    return {"status": "deleted"}
