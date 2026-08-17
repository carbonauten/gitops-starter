from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import ReputationDeletionRequest, ReputationMention, get_db
from ..dependencies import require_editor
from ..reputation_crawler import mention_to_dict
from ..reputation_service import (
    close_deletion,
    deletion_to_dict,
    list_mentions,
    request_deletion,
    start_crawl,
    summary,
)

router = APIRouter(prefix="/api/reputation", tags=["reputation"])


class DeletionCreateRequest(BaseModel):
    reason: str = Field(default="other", max_length=40)
    notes: str = Field(default="", max_length=4000)
    publisher_email: str = Field(default="", max_length=200)


@router.get("/summary")
def reputation_summary(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
) -> dict:
    return summary(db)


@router.get("/mentions")
def reputation_mentions(
    sentiment: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
) -> dict:
    rows = list_mentions(db, sentiment=sentiment, query=q)
    return {
        "mentions": [
            mention_to_dict(row, deletion_to_dict(deletion) if deletion else None) for row, deletion in rows
        ]
    }


@router.post("/crawl")
def reputation_crawl(
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    run = start_crawl(db, actor=user)
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "found": run.found,
            "created": run.created,
            "updated": run.updated,
            "negative": run.negative,
            "error": run.error,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }
    }


@router.post("/mentions/{mention_id}/deletion-requests", status_code=201)
def create_deletion_request(
    mention_id: str,
    payload: DeletionCreateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    mention = db.get(ReputationMention, mention_id)
    if not mention:
        raise HTTPException(status_code=404, detail="not_found")
    row = request_deletion(
        db,
        mention,
        reason=payload.reason,
        notes=payload.notes,
        publisher_email=payload.publisher_email,
        actor=user,
    )
    return {"request": deletion_to_dict(row), "mention": mention_to_dict(mention, deletion_to_dict(row))}


@router.patch("/deletion-requests/{request_id}/close")
def close_deletion_request(
    request_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    row = db.get(ReputationDeletionRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    row = close_deletion(db, row, actor=user)
    mention = db.get(ReputationMention, row.mention_id)
    return {
        "request": deletion_to_dict(row),
        "mention": mention_to_dict(mention, deletion_to_dict(row)) if mention else None,
    }
