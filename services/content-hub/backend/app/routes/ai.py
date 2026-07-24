from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ai_service import ai_configured, summarize_article, translate_article
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


class TranslateRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100_000)
    target_language: str = Field(pattern="^(de|en|zh-CN)$")
    source_language: Optional[str] = Field(default=None, pattern="^(de|en|zh-CN)$")


class SummarizeRequest(BaseModel):
    title: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=100_000)
    language: str = Field(default="de", pattern="^(de|en|zh-CN)$")


def _require_ai() -> None:
    if not ai_configured():
        raise HTTPException(status_code=503, detail="ai_not_configured")


@router.get("/status")
def ai_status(_user: dict = Depends(get_current_user)) -> dict:
    return {
        "available": ai_configured(),
        "features": ["search_ask", "translate", "summarize"],
        "assistant_name": "Ask Carbonauten",
    }


@router.post("/translate")
def translate_content(
    payload: TranslateRequest,
    _user: dict = Depends(get_current_user),
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
    _user: dict = Depends(get_current_user),
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
