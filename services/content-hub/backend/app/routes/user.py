from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import get_session, require_user, set_session
from ..config import get_settings
from ..i18n import normalize_language, translate

router = APIRouter(prefix="/api/user", tags=["user"])


class LanguageUpdate(BaseModel):
    language: str = Field(..., description="de, en, or zh-CN")


@router.patch("/language")
def update_language(payload: LanguageUpdate, request: Request, response: Response) -> dict:
    language = normalize_language(payload.language)
    if language not in get_settings().supported_languages:
        raise HTTPException(status_code=400, detail="invalid_language")

    user = require_user(request)
    user["language"] = language

    session = get_session(request) or {}
    session["user"] = user
    set_session(response, session)

    return {
        "user": user,
        "message": translate("messages.language_updated", language),
    }
