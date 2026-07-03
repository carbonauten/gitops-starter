from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import Article, Certificate, get_db
from ..dependencies import get_current_user
from ..version_service import compare_versions, get_revision, list_revisions

router = APIRouter(prefix="/api/versions", tags=["versions"])

VALID_ENTITY_TYPES = {"article", "certificate"}


def _ensure_entity_exists(db: Session, entity_type: str, entity_id: str) -> None:
    if entity_type == "article":
        if not db.get(Article, entity_id):
            raise HTTPException(status_code=404, detail="not_found")
    elif entity_type == "certificate":
        if not db.get(Certificate, entity_id):
            raise HTTPException(status_code=404, detail="not_found")
    else:
        raise HTTPException(status_code=422, detail="validation")


@router.get("/{entity_type}/{entity_id}")
def list_entity_versions(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="validation")
    _ensure_entity_exists(db, entity_type, entity_id)
    return {"versions": list_revisions(db, entity_type=entity_type, entity_id=entity_id)}


@router.get("/{entity_type}/{entity_id}/compare")
def compare_entity_versions(
    entity_type: str,
    entity_id: str,
    from_version: int = Query(..., ge=1),
    to_version: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    if entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="validation")
    _ensure_entity_exists(db, entity_type, entity_id)
    return compare_versions(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        from_version=from_version,
        to_version=to_version,
    )


@router.get("/revision/{revision_id}")
def get_version_detail(
    revision_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"version": get_revision(db, revision_id)}
