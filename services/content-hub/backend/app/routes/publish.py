from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user, require_editor, require_it_master
from ..publish_service import (
    ensure_publish_settings,
    list_channels,
    list_publications,
    publish_article,
    retry_delivery,
    run_certificate_reminders,
    settings_to_dict,
    update_publish_settings,
)

router = APIRouter(prefix="/api/publish", tags=["publish"])


class PublishArticleRequest(BaseModel):
    channels: list[str] = Field(..., min_length=1)


class PublishSettingsUpdate(BaseModel):
    teams_enabled: Optional[bool] = None
    teams_team_id: Optional[str] = None
    teams_channel_id: Optional[str] = None
    outlook_enabled: Optional[bool] = None
    outlook_sender_id: Optional[str] = None
    notion_enabled: Optional[bool] = None
    notion_database_id: Optional[str] = None


@router.get("/channels")
def get_channels(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    channels = list_channels(db)
    return {"channels": channels}


@router.get("/settings")
def get_settings_route(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    row = ensure_publish_settings(db)
    return {"settings": settings_to_dict(row)}


@router.patch("/settings")
def patch_settings(
    payload: PublishSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    settings = update_publish_settings(db, payload.model_dump(exclude_unset=True))
    return {"settings": settings}


@router.get("/history")
def get_history(
    resource_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {"publications": list_publications(db, resource_id=resource_id)}


@router.post("/articles/{article_id}")
async def publish_article_route(
    article_id: str,
    payload: PublishArticleRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_editor),
) -> dict:
    publication = await publish_article(
        db,
        article_id=article_id,
        channels=payload.channels,
        user=user,
    )
    return {"publication": publication}


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery_route(
    delivery_id: str,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_editor),
) -> dict:
    delivery = await retry_delivery(db, delivery_id)
    return {"delivery": delivery}


@router.post("/certificate-reminders")
async def certificate_reminders_route(
    db: Session = Depends(get_db),
    user: dict = Depends(require_it_master),
) -> dict:
    return await run_certificate_reminders(db, user=user)
