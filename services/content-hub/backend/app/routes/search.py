from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..ai_service import ai_configured, expand_search_query, generate_search_answer, suggest_follow_up_queries
from ..dependencies import get_current_user
from ..database import get_db
from ..schemas import SearchAskRequest
from ..search_service import (
    build_keyword_answer,
    build_suggestions,
    enrich_context_for_ask,
    extract_keywords,
    search_content,
)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(
    q: str = Query(min_length=1),
    type: Optional[Literal["article", "file", "certificate"]] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    results, counts = search_content(db, q, result_type=type, limit=limit)
    return {
        "query": q,
        "results": results,
        "counts": counts,
        "ai_available": ai_configured(),
        "assistant_name": "Ask Carbonauten",
    }


@router.post("/ask")
def ask_search(
    payload: SearchAskRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    language = payload.language or user.get("language") or "de"
    search_query = payload.question.strip()
    mode = "keyword"

    if ai_configured():
        expanded = expand_search_query(payload.question, language=language)
        if expanded:
            search_query = expanded
            mode = "ai"

    if search_query == payload.question.strip():
        keyword_query = extract_keywords(payload.question)
        if keyword_query:
            search_query = keyword_query

    results, counts = search_content(
        db,
        search_query,
        result_type=payload.type,
        limit=12,
    )

    answer = ""
    if ai_configured():
        enriched = enrich_context_for_ask(db, results)
        ai_answer = generate_search_answer(
            payload.question,
            results,
            language=language,
            enriched_context=enriched,
        )
        if ai_answer:
            answer = ai_answer
            mode = "ai"

    if not answer:
        answer = build_keyword_answer(payload.question, results) or ""

    suggestions = suggest_follow_up_queries(payload.question, results, language=language)
    if not suggestions:
        suggestions = build_suggestions(db, limit=5)

    return {
        "question": payload.question,
        "search_query": search_query,
        "answer": answer,
        "mode": mode,
        "results": results,
        "counts": counts,
        "suggested_queries": suggestions,
        "ai_available": ai_configured(),
        "assistant_name": "Ask Carbonauten",
    }


@router.get("/suggestions")
def search_suggestions(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    return {
        "suggestions": build_suggestions(db),
        "ai_available": ai_configured(),
        "assistant_name": "Ask Carbonauten",
    }


@router.get("/folders")
def list_folders(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    from sqlalchemy import select

    from ..database import FileAsset

    folders = db.scalars(select(FileAsset.folder).distinct().order_by(FileAsset.folder)).all()
    return {"folders": folders}
