from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ai_service import (
    ai_configured,
    draft_article_from_notes,
    rewrite_article,
    summarize_article,
    translate_article,
)
from ..config import get_settings
from ..dependencies import get_current_user, require_editor

router = APIRouter(prefix="/api/ai", tags=["ai"])

ToneLiteral = Literal["professional", "concise", "friendly", "formal"]
LangLiteral = Literal["de", "en", "zh-CN"]


class TranslateRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100_000)
    target_language: str = Field(pattern="^(de|en|zh-CN)$")
    source_language: Optional[str] = Field(default=None, pattern="^(de|en|zh-CN)$")


class SummarizeRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100_000)
    language: str = Field(default="de", pattern="^(de|en|zh-CN)$")


class RewriteRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100_000)
    tone: ToneLiteral = "professional"
    language: Optional[LangLiteral] = None


class DraftFromNotesRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=20_000)
    language: LangLiteral = "de"
    title_hint: str = Field(default="", max_length=500)


def _require_ai() -> None:
    if not ai_configured():
        raise HTTPException(status_code=503, detail="ai_not_configured")


@router.get("/status")
def ai_status(_user: dict = Depends(get_current_user)) -> dict:
    features = [
        "search_ask",
        "translate",
        "summarize",
        "rewrite",
        "draft_from_notes",
        "m365_directory",
        "m365_function_calling",
    ]
    if get_settings().embeddings_configured:
        features.append("semantic_search")
    return {
        "available": ai_configured(),
        "embeddings_available": get_settings().embeddings_configured,
        "features": features,
        "assistant_name": "Ask Carbonauten",
    }


@router.post("/translate")
def translate_content(
    payload: TranslateRequest,
    _user: dict = Depends(require_editor),
) -> dict:
    _require_ai()
    if not payload.title.strip() and not payload.content.strip():
        raise HTTPException(status_code=400, detail="empty_content")
    result = translate_article(
        title=payload.title,
        content=payload.content,
        target_language=payload.target_language,
        source_language=payload.source_language,
    )
    if not result:
        raise HTTPException(status_code=502, detail="ai_translation_failed")
    return {"translation": result, "assistant_name": "Ask Carbonauten"}


@router.post("/summarize")
def summarize_content(
    payload: SummarizeRequest,
    _user: dict = Depends(require_editor),
) -> dict:
    _require_ai()
    if not payload.title.strip() and not payload.content.strip():
        raise HTTPException(status_code=400, detail="empty_content")
    summary = summarize_article(
        title=payload.title,
        content=payload.content,
        language=payload.language,
    )
    if not summary:
        raise HTTPException(status_code=502, detail="ai_summary_failed")
    return {"summary": summary, "assistant_name": "Ask Carbonauten"}


@router.post("/rewrite")
def rewrite_content(
    payload: RewriteRequest,
    _user: dict = Depends(require_editor),
) -> dict:
    _require_ai()
    if not payload.title.strip() and not payload.content.strip():
        raise HTTPException(status_code=400, detail="empty_content")
    result = rewrite_article(
        title=payload.title,
        content=payload.content,
        tone=payload.tone,
        language=payload.language,
    )
    if not result:
        raise HTTPException(status_code=502, detail="ai_rewrite_failed")
    return {"rewrite": result, "assistant_name": "Ask Carbonauten"}


@router.post("/draft-from-notes")
def draft_from_notes(
    payload: DraftFromNotesRequest,
    _user: dict = Depends(require_editor),
) -> dict:
    _require_ai()
    if not payload.notes.strip():
        raise HTTPException(status_code=400, detail="empty_notes")
    result = draft_article_from_notes(
        notes=payload.notes,
        language=payload.language,
        title_hint=payload.title_hint,
    )
    if not result:
        raise HTTPException(status_code=502, detail="ai_draft_failed")
    return {"draft": result, "assistant_name": "Ask Carbonauten"}
