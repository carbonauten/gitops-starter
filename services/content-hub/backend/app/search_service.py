from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .certificates import compute_certificate_status
from .database import Article, Certificate, FileAsset
from .schemas import SearchResult

SearchType = Literal["article", "file", "certificate"]
HTML_TAG_RE = re.compile(r"<[^>]+>")
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "could", "should", "may", "might", "must", "shall", "can",
    "what", "which", "who", "whom", "whose", "where", "when", "why", "how", "this", "that",
    "these", "those", "i", "you", "he", "she", "it", "we", "they", "my", "your", "our",
    "der", "die", "das", "ein", "eine", "und", "oder", "ist", "sind", "was", "wie", "wo",
    "wann", "warum", "welche", "welcher", "welches", "für", "mit", "von", "zu", "im", "am",
}


def extract_keywords(question: str) -> str:
    words = [
        word
        for word in re.split(r"[^\wäöüÄÖÜß]+", question.lower())
        if len(word) >= 3 and word not in STOPWORDS
    ]
    if not words:
        return question.strip()
    return " ".join(words[:6])


def _clean_text(text: str) -> str:
    return " ".join(HTML_TAG_RE.sub(" ", text or "").split())


def _snippet(text: str, query: str, max_len: int = 160) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    lower = cleaned.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        return cleaned[:max_len]
    start = max(0, idx - 50)
    excerpt = cleaned[start : start + max_len].strip()
    if start > 0:
        excerpt = f"…{excerpt}"
    if start + max_len < len(cleaned):
        excerpt = f"{excerpt}…"
    return excerpt


def _relevance_score(title: str, snippet: str, query: str) -> float:
    q = query.lower().strip()
    if not q:
        return 0.0
    title_l = title.lower()
    snippet_l = snippet.lower()
    terms = [term for term in re.split(r"\s+", q) if len(term) >= 2]
    score = 0.0
    if q in title_l:
        score += 12.0
    if q in snippet_l:
        score += 6.0
    for term in terms:
        if term in title_l:
            score += 3.0
        if term in snippet_l:
            score += 1.0
    return score


def search_content(
    db: Session,
    query: str,
    *,
    result_type: Optional[SearchType] = None,
    limit: int = 30,
) -> tuple[list[SearchResult], dict[str, int]]:
    q = query.strip()
    if not q:
        return [], {"article": 0, "file": 0, "certificate": 0}

    pattern = f"%{q}%"
    results: list[SearchResult] = []

    if result_type in (None, "article"):
        articles = db.scalars(
            select(Article)
            .where(or_(Article.title.ilike(pattern), Article.content.ilike(pattern)))
            .order_by(Article.updated_at.desc())
            .limit(limit)
        ).all()
        for article in articles:
            snippet = _snippet(article.content, q)
            title = article.title or "Untitled"
            results.append(
                SearchResult(
                    type="article",
                    id=article.id,
                    title=title,
                    snippet=snippet,
                    status=article.status,
                    updated_at=article.updated_at,
                    relevance=_relevance_score(title, snippet, q),
                )
            )

    if result_type in (None, "file"):
        files = db.scalars(
            select(FileAsset)
            .where(or_(FileAsset.original_name.ilike(pattern), FileAsset.folder.ilike(pattern)))
            .order_by(FileAsset.created_at.desc())
            .limit(limit)
        ).all()
        for file_asset in files:
            snippet = file_asset.folder or ""
            results.append(
                SearchResult(
                    type="file",
                    id=file_asset.id,
                    title=file_asset.original_name,
                    snippet=snippet,
                    folder=file_asset.folder,
                    updated_at=file_asset.created_at,
                    relevance=_relevance_score(file_asset.original_name, snippet, q),
                )
            )

    if result_type in (None, "certificate"):
        certificates = db.scalars(
            select(Certificate)
            .where(
                or_(
                    Certificate.name.ilike(pattern),
                    Certificate.issuer.ilike(pattern),
                    Certificate.responsible_name.ilike(pattern),
                    Certificate.notes.ilike(pattern),
                )
            )
            .order_by(Certificate.updated_at.desc())
            .limit(limit)
        ).all()
        for certificate in certificates:
            snippet = certificate.issuer or certificate.category
            if certificate.notes:
                snippet = _snippet(certificate.notes, q, max_len=120) or snippet
            results.append(
                SearchResult(
                    type="certificate",
                    id=certificate.id,
                    title=certificate.name,
                    snippet=snippet,
                    status=compute_certificate_status(
                        certificate.valid_to,
                        certificate.renewal_in_progress,
                    ),
                    updated_at=certificate.updated_at,
                    relevance=_relevance_score(certificate.name, snippet, q),
                )
            )

    results.sort(
        key=lambda item: (
            item.relevance or 0.0,
            item.updated_at if isinstance(item.updated_at, datetime) else datetime.min,
        ),
        reverse=True,
    )

    counts = {
        "article": sum(1 for item in results if item.type == "article"),
        "file": sum(1 for item in results if item.type == "file"),
        "certificate": sum(1 for item in results if item.type == "certificate"),
    }
    return results[:limit], counts


def build_suggestions(db: Session, limit: int = 8) -> list[str]:
    suggestions: list[str] = []
    articles = db.scalars(select(Article.title).order_by(Article.updated_at.desc()).limit(limit)).all()
    for title in articles:
        cleaned = (title or "").strip()
        if cleaned and cleaned not in suggestions:
            suggestions.append(cleaned)
    certificates = db.scalars(select(Certificate.name).order_by(Certificate.updated_at.desc()).limit(limit)).all()
    for name in certificates:
        cleaned = (name or "").strip()
        if cleaned and cleaned not in suggestions:
            suggestions.append(cleaned)
    return suggestions[:limit]


def build_keyword_answer(question: str, results: list[SearchResult]) -> str:
    if not results:
        return ""
    lines = [f"• {item.title}: {item.snippet or '—'}" for item in results[:5]]
    return f"{question.strip()}\n\n" + "\n".join(lines)
