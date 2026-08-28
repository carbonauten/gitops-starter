"""Semantic search: text embeddings for articles, files and certificates.

Complements the keyword search in search_service.py. Keyword search misses
paraphrases and cross-language phrasing ("Wo ist die Kündigungsfrist?" won't
match an article titled "Notice periods"); cosine similarity over embeddings
catches those. Embeddings are cached in ContentEmbedding (keyed by a hash of
the source text) so unchanged content is never re-sent to the API.

Vectors are stored as JSON in a text column and compared in pure Python —
no pgvector/numpy dependency. Fine for an internal knowledge base of a few
thousand documents; would need a real vector index far beyond that scale.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .certificates import compute_certificate_status
from .config import Settings, get_settings
from .database import Article, Certificate, ContentEmbedding, FileAsset
from .schemas import SearchResult

logger = logging.getLogger(__name__)

HTML_TAG_RE_REPLACEMENT = " "
_MIN_SIMILARITY = 0.72  # below this, a "semantic" match is more likely noise than signal
_MAX_EMBED_CHARS = 8000


def _clean_text(text: str) -> str:
    import re

    return " ".join(re.sub(r"<[^>]+>", HTML_TAG_RE_REPLACEMENT, text or "").split())


def _embedding_model_name(settings: Settings) -> str:
    if settings.azure_openai_endpoint.strip() and settings.azure_openai_api_key.strip():
        return f"azure:{settings.azure_openai_embedding_deployment}"
    return f"openai:{settings.openai_embedding_model}"


def generate_embedding(text: str, *, settings: Settings | None = None) -> list[float] | None:
    settings = settings or get_settings()
    if not settings.embeddings_configured:
        return None
    clipped = (text or "").strip()[:_MAX_EMBED_CHARS]
    if not clipped:
        return None

    try:
        if settings.azure_openai_endpoint.strip() and settings.azure_openai_api_key.strip():
            url = (
                f"{settings.azure_openai_endpoint.rstrip('/')}"
                f"/openai/deployments/{settings.azure_openai_embedding_deployment}"
                f"/embeddings?api-version=2024-06-01"
            )
            headers = {"api-key": settings.azure_openai_api_key.strip(), "Content-Type": "application/json"}
            body: dict[str, Any] = {"input": clipped}
        else:
            url = "https://api.openai.com/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {settings.openai_api_key.strip()}",
                "Content-Type": "application/json",
            }
            body = {"model": settings.openai_embedding_model.strip() or "text-embedding-3-small", "input": clipped}

        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data") or []
        if not data:
            return None
        vector = data[0].get("embedding")
        if not isinstance(vector, list) or not vector:
            return None
        return [float(value) for value in vector]
    except Exception:  # noqa: BLE001
        logger.exception("Embedding request failed")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _entity_text(db: Session, entity_type: str, entity_id: str) -> str | None:
    """Text to embed for one entity, or None if it no longer exists."""
    if entity_type == "article":
        article = db.get(Article, entity_id)
        if not article:
            return None
        return f"{article.title}\n\n{_clean_text(article.content)}"
    if entity_type == "certificate":
        certificate = db.get(Certificate, entity_id)
        if not certificate:
            return None
        parts = [certificate.name, certificate.category, certificate.issuer, _clean_text(certificate.notes)]
        return "\n".join(part for part in parts if part)
    if entity_type == "file":
        file_asset = db.get(FileAsset, entity_id)
        if not file_asset:
            return None
        return f"{file_asset.original_name}\n{file_asset.folder or ''}"
    return None


def embed_text_for_entity(db: Session, *, entity_type: str, entity_id: str, text: str) -> bool:
    """Compute and store the embedding for one entity. Skips the API call when the
    text is unchanged AND it was embedded with the currently configured model —
    switching AZURE_OPENAI_EMBEDDING_DEPLOYMENT / OPENAI_EMBEDDING_MODEL and
    reindexing must actually refresh vectors, not just no-op on unchanged text.
    Returns True on a stored/kept embedding."""
    settings = get_settings()
    clean = (text or "").strip()
    if not clean:
        return False
    text_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
    current_model = _embedding_model_name(settings)

    existing = db.scalar(
        select(ContentEmbedding).where(
            ContentEmbedding.entity_type == entity_type, ContentEmbedding.entity_id == entity_id
        )
    )
    if existing and existing.text_hash == text_hash and existing.model == current_model:
        return True

    vector = generate_embedding(clean, settings=settings)
    if vector is None:
        return False

    if existing:
        existing.text_hash = text_hash
        existing.embedding = json.dumps(vector)
        existing.model = current_model
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(
            ContentEmbedding(
                entity_type=entity_type,
                entity_id=entity_id,
                text_hash=text_hash,
                embedding=json.dumps(vector),
                model=current_model,
            )
        )
    db.commit()
    return True


def delete_embedding(db: Session, *, entity_type: str, entity_id: str) -> None:
    """Drop a cached embedding when its entity is deleted, so semantic search
    doesn't keep scoring a row that will 404 on lookup."""
    existing = db.scalar(
        select(ContentEmbedding).where(
            ContentEmbedding.entity_type == entity_type, ContentEmbedding.entity_id == entity_id
        )
    )
    if existing:
        db.delete(existing)
        db.commit()


def reembed_entity(db: Session, *, entity_type: str, entity_id: str) -> bool:
    text = _entity_text(db, entity_type, entity_id)
    if text is None:
        return False
    return embed_text_for_entity(db, entity_type=entity_type, entity_id=entity_id, text=text)


def reembed_entity_task(entity_type: str, entity_id: str) -> None:
    """FastAPI BackgroundTasks entry point: opens its own DB session (the request's
    session is closed by the time this runs)."""
    from .database import _SessionLocal

    db = _SessionLocal()
    try:
        reembed_entity(db, entity_type=entity_type, entity_id=entity_id)
    except Exception:  # noqa: BLE001
        logger.exception("Background re-embed failed for %s/%s", entity_type, entity_id)
    finally:
        db.close()


def queue_reembed(background_tasks: Any, *, entity_type: str, entity_id: str) -> None:
    """Schedule a re-embed after the response is sent. No-op when embeddings aren't
    configured, so create/update requests stay fast when this feature is unused."""
    if not get_settings().embeddings_configured:
        return
    background_tasks.add_task(reembed_entity_task, entity_type, entity_id)


def _result_for_row(entity_type: str, row: Any, similarity: float) -> SearchResult | None:
    if entity_type == "article":
        return SearchResult(
            type="article",
            id=row.id,
            title=row.title or "Untitled",
            snippet=_clean_text(row.content)[:160],
            status=row.status,
            updated_at=row.updated_at,
            relevance=similarity * 10,
        )
    if entity_type == "certificate":
        return SearchResult(
            type="certificate",
            id=row.id,
            title=row.name,
            snippet=row.issuer or row.category,
            status=compute_certificate_status(row.valid_to, row.renewal_in_progress),
            updated_at=row.updated_at,
            relevance=similarity * 10,
        )
    if entity_type == "file":
        return SearchResult(
            type="file",
            id=row.id,
            title=row.original_name,
            snippet=row.folder or "",
            folder=row.folder,
            updated_at=row.created_at,
            relevance=similarity * 10,
        )
    return None


_ENTITY_MODEL = {"article": Article, "certificate": Certificate, "file": FileAsset}


def semantic_search_content(
    db: Session,
    query: str,
    *,
    result_type: str | None = None,
    limit: int = 12,
) -> list[SearchResult]:
    """Rank indexed content by cosine similarity to the query. Returns [] when
    embeddings aren't configured or nothing is indexed yet — callers fall back
    to keyword search in that case, this never replaces it."""
    settings = get_settings()
    if not settings.embeddings_configured:
        return []
    query_vector = generate_embedding(query, settings=settings)
    if query_vector is None:
        return []

    stmt = select(ContentEmbedding)
    if result_type:
        stmt = stmt.where(ContentEmbedding.entity_type == result_type)
    rows = db.scalars(stmt).all()

    scored: list[tuple[float, str, str]] = []
    for row in rows:
        try:
            vector = json.loads(row.embedding)
        except (TypeError, ValueError):
            continue
        similarity = cosine_similarity(query_vector, vector)
        if similarity >= _MIN_SIMILARITY:
            scored.append((similarity, row.entity_type, row.entity_id))
    scored.sort(key=lambda item: item[0], reverse=True)

    results: list[SearchResult] = []
    for similarity, entity_type, entity_id in scored[: limit * 2]:  # a few may 404 (deleted, not yet re-indexed)
        model = _ENTITY_MODEL.get(entity_type)
        if not model:
            continue
        entity = db.get(model, entity_id)
        if not entity:
            continue
        result = _result_for_row(entity_type, entity, similarity)
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def reindex_all(db: Session, *, limit_per_type: int = 500) -> dict[str, int]:
    """Backfill/refresh embeddings for existing content. Synchronous and rate-limited
    by limit_per_type — an internal knowledge base, not a bulk-ingest pipeline; run it
    again to pick up whatever it didn't get to."""
    counts = {"article": 0, "certificate": 0, "file": 0, "skipped": 0, "failed": 0}
    if not get_settings().embeddings_configured:
        return counts

    for entity_type, model, order_col in (
        ("article", Article, Article.updated_at),
        ("certificate", Certificate, Certificate.updated_at),
        ("file", FileAsset, FileAsset.created_at),
    ):
        rows = db.scalars(select(model).order_by(order_col.desc()).limit(limit_per_type)).all()
        for row in rows:
            ok = reembed_entity(db, entity_type=entity_type, entity_id=row.id)
            if ok:
                counts[entity_type] += 1
            else:
                counts["failed"] += 1
    return counts
