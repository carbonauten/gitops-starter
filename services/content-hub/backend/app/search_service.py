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
    "there", "here", "any", "all", "some", "about", "into", "from",
    "der", "die", "das", "ein", "eine", "und", "oder", "ist", "sind", "was", "wie", "wo",
    "wann", "warum", "welche", "welcher", "welches", "welchen", "für", "mit", "von", "zu",
    "im", "am", "gibt", "gibts", "noch", "auch", "nur", "bitte", "alle", "alles", "hier",
    "dort", "mehr", "bereits", "schon", "mal", "uns", "euch", "mir", "dir", "ihm", "ihr",
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


def _term_variants(term: str) -> list[str]:
    variants = {term.lower()}
    if term.endswith(("en", "es", "er")) and len(term) > 4:
        variants.add(term[:-2])
    if term.endswith("e") and len(term) > 3:
        variants.add(term[:-1])
    if term.endswith("n") and len(term) > 4:
        variants.add(term[:-1])
    return [item for item in variants if len(item) >= 2]


def _query_terms(query: str) -> list[str]:
    raw = [term for term in re.split(r"\s+", query.strip().lower()) if len(term) >= 2]
    terms: list[str] = []
    seen: set[str] = set()
    for term in raw:
        for variant in _term_variants(term):
            if variant not in seen:
                seen.add(variant)
                terms.append(variant)
    return terms or ([query.strip()] if query.strip() else [])


def looks_like_certificate_inventory(question: str) -> bool:
    q = question.lower()
    mentions_cert = any(
        token in q
        for token in ("zertifikat", "zertifikate", "certificate", "certificates", "iso ")
    )
    inventory = any(
        token in q
        for token in ("welche", "which", "was gibt", "gibt es", "liste", "list", "alle", "overview", "überblick")
    )
    return mentions_cert and inventory


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

    terms = _query_terms(q)
    results: list[SearchResult] = []

    if result_type in (None, "article"):
        article_filters = []
        for term in terms:
            pattern = f"%{term}%"
            article_filters.extend(
                [
                    Article.title.ilike(pattern),
                    Article.content.ilike(pattern),
                ]
            )
        articles = db.scalars(
            select(Article)
            .where(or_(*article_filters))
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
        file_filters = []
        for term in terms:
            pattern = f"%{term}%"
            file_filters.extend(
                [
                    FileAsset.original_name.ilike(pattern),
                    FileAsset.folder.ilike(pattern),
                ]
            )
        files = db.scalars(
            select(FileAsset)
            .where(or_(*file_filters))
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
        certificate_filters = []
        for term in terms:
            pattern = f"%{term}%"
            certificate_filters.extend(
                [
                    Certificate.name.ilike(pattern),
                    Certificate.issuer.ilike(pattern),
                    Certificate.responsible_name.ilike(pattern),
                    Certificate.notes.ilike(pattern),
                    Certificate.category.ilike(pattern),
                ]
            )
        certificates = db.scalars(
            select(Certificate)
            .where(or_(*certificate_filters))
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


def merge_results(
    primary: list[SearchResult],
    secondary: list[SearchResult],
    *,
    limit: int = 30,
) -> list[SearchResult]:
    """Union keyword results with semantic-search results, deduplicated by (type, id).

    A hit found by both keyword and semantic search gets a relevance boost — it's
    the strongest signal we have that it's actually what the user wants.
    """
    by_key: dict[tuple[str, str], SearchResult] = {(item.type, item.id): item for item in primary}
    for item in secondary:
        key = (item.type, item.id)
        existing = by_key.get(key)
        if existing:
            existing.relevance = (existing.relevance or 0.0) + (item.relevance or 0.0) * 0.25
        else:
            by_key[key] = item

    merged = list(by_key.values())
    merged.sort(
        key=lambda entry: (
            entry.relevance or 0.0,
            entry.updated_at if isinstance(entry.updated_at, datetime) else datetime.min,
        ),
        reverse=True,
    )
    return merged[:limit]


def count_by_type(results: list[SearchResult]) -> dict[str, int]:
    return {
        "article": sum(1 for item in results if item.type == "article"),
        "file": sum(1 for item in results if item.type == "file"),
        "certificate": sum(1 for item in results if item.type == "certificate"),
    }


def list_recent_certificates(db: Session, *, limit: int = 12) -> list[SearchResult]:
    certificates = db.scalars(
        select(Certificate).order_by(Certificate.updated_at.desc()).limit(limit)
    ).all()
    results: list[SearchResult] = []
    for certificate in certificates:
        status = compute_certificate_status(certificate.valid_to, certificate.renewal_in_progress)
        snippet = f"{certificate.issuer or certificate.category} · gültig bis {certificate.valid_to}"
        results.append(
            SearchResult(
                type="certificate",
                id=certificate.id,
                title=certificate.name,
                snippet=snippet,
                status=status,
                updated_at=certificate.updated_at,
                relevance=1.0,
            )
        )
    return results


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
    if looks_like_certificate_inventory(question):
        certs = [item for item in results if item.type == "certificate"]
        if certs:
            lines = [f"• {item.title}: {item.snippet or '—'}" for item in certs[:8]]
            return "Aktuelle Zertifikate in der Platform:\n\n" + "\n".join(lines)
    lines = [f"• {item.title}: {item.snippet or '—'}" for item in results[:5]]
    return f"{question.strip()}\n\n" + "\n".join(lines)


def enrich_context_for_ask(db: Session, results: list[SearchResult], limit: int = 6) -> list[str]:
    """Load fuller source text for Ask Carbonauten RAG answers."""
    blocks: list[str] = []
    for index, item in enumerate(results[:limit], start=1):
        if item.type == "article":
            article = db.get(Article, item.id)
            body = _clean_text(article.content if article else item.snippet)[:1200]
            blocks.append(
                f"[{index}] type=article title={item.title}\nstatus={item.status or '-'}\ncontent={body}"
            )
        elif item.type == "certificate":
            certificate = db.get(Certificate, item.id)
            if certificate:
                notes = _clean_text(certificate.notes)[:400]
                blocks.append(
                    f"[{index}] type=certificate title={certificate.name}\n"
                    f"issuer={certificate.issuer} category={certificate.category} "
                    f"valid_to={certificate.valid_to} status={item.status or '-'}\nnotes={notes}"
                )
            else:
                blocks.append(f"[{index}] type=certificate title={item.title}\nsnippet={item.snippet}")
        else:
            blocks.append(
                f"[{index}] type=file title={item.title}\nfolder={item.folder or item.snippet or '-'}"
            )
    return blocks
