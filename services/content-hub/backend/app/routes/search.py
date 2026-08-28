from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..audit_service import log_audit
from ..ai_service import ai_configured, expand_search_query, generate_search_answer, suggest_follow_up_queries
from ..config import get_settings
from ..dependencies import get_current_user, require_it_master
from ..database import get_db
from ..embedding_service import reindex_all, semantic_search_content
from ..m365_ai_service import handle_directory_question, looks_like_m365_admin_question
from ..roles import ROLE_IT_MASTER
from ..schemas import SearchAskRequest
from ..search_service import (
    build_keyword_answer,
    build_suggestions,
    count_by_type,
    enrich_context_for_ask,
    extract_keywords,
    list_recent_certificates,
    looks_like_certificate_inventory,
    merge_results,
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
    if get_settings().embeddings_configured:
        semantic_results = semantic_search_content(db, q, result_type=type, limit=limit)
        if semantic_results:
            results = merge_results(results, semantic_results, limit=limit)
            counts = count_by_type(results)
    return {
        "query": q,
        "results": results,
        "counts": counts,
        "ai_available": ai_configured(),
        "assistant_name": "Ask Carbonauten",
    }


@router.post("/ask")
async def ask_search(
    payload: SearchAskRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict:
    language = payload.language or user.get("language") or "de"
    if user.get("role") == ROLE_IT_MASTER and looks_like_m365_admin_question(payload.question):
        directory = await handle_directory_question(payload.question, language=language)
        if directory.get("action") in {"create", "disable", "enable", "reset_password"} and directory.get("user"):
            log_audit(
                db,
                entity_type="m365_user",
                entity_id=directory["user"]["id"],
                action=f"ai_{directory['action']}",
                actor=user,
                details={"question": payload.question[:300], "upn": directory["user"].get("user_principal_name")},
            )
        return {
            "question": payload.question,
            "search_query": payload.question.strip(),
            "answer": directory["answer"],
            "mode": "ai",
            "results": [],
            "counts": {"article": 0, "file": 0, "certificate": 0},
            "suggested_queries": [
                "Welche M365 Benutzer gibt es?",
                "Sperre chibi.guest@carbonauten.com",
                "Lege user anna@carbonauten.com an",
            ],
            "ai_available": ai_configured(),
            "assistant_name": "Ask Carbonauten",
            "m365_action": directory.get("action"),
        }

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

    # Semantic search catches paraphrases keyword matching misses (different wording,
    # a question in a different language than the source article) — merge it in before
    # building the RAG context so Ask Carbonauten's answer draws on those sources too.
    if get_settings().embeddings_configured:
        semantic_results = semantic_search_content(db, payload.question, result_type=payload.type, limit=12)
        if semantic_results:
            results = merge_results(results, semantic_results, limit=12)
            counts = count_by_type(results)

    # Broad questions like "welche Zertifikate gibt es?" should list certificates
    # even when the word "Zertifikat" is not part of a certificate name.
    if not results and looks_like_certificate_inventory(payload.question) and payload.type in (None, "certificate"):
        results = list_recent_certificates(db, limit=12)
        counts = {
            "article": 0,
            "file": 0,
            "certificate": len(results),
        }
        search_query = "certificates"

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
        "embeddings_available": get_settings().embeddings_configured,
        "assistant_name": "Ask Carbonauten",
    }


@router.post("/reindex")
def reindex_search(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_it_master),
) -> dict:
    """Backfill/refresh semantic-search embeddings for existing content.

    New and edited content is embedded automatically in the background; this manual
    trigger is for the one-time backfill after configuring embeddings, or after
    switching to a different embedding model/deployment.
    """
    counts = reindex_all(db)
    return {"counts": counts, "embeddings_available": get_settings().embeddings_configured}


@router.get("/folders")
def list_folders(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict:
    from sqlalchemy import select

    from ..database import FileAsset

    folders = db.scalars(select(FileAsset.folder).distinct().order_by(FileAsset.folder)).all()
    return {"folders": folders}
