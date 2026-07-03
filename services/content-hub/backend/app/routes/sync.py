from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import require_it_master
from ..sync_service import (
    export_sync_payload,
    import_sync_payload,
    pull_from_peer,
    push_to_peer,
    run_full_sync,
    sync_status,
)

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _verify_sync_key(x_sync_key: Optional[str] = Header(default=None)) -> None:
    settings = get_settings()
    expected = settings.sync_api_key.strip()
    if not expected or not x_sync_key or x_sync_key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.get("/status")
def get_sync_status(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return sync_status(db)


@router.post("/run")
async def trigger_sync(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return await run_full_sync(db)


@router.post("/push")
async def trigger_push(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return await push_to_peer(db)


@router.post("/pull")
async def trigger_pull(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_it_master),
) -> dict:
    return await pull_from_peer(db)


@router.get("/export")
def sync_export(
    db: Session = Depends(get_db),
    _: None = Depends(_verify_sync_key),
) -> dict:
    return export_sync_payload(db)


@router.post("/import")
def sync_import(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_sync_key),
) -> dict:
    return import_sync_payload(db, payload)
