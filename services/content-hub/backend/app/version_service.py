from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .database import Article, Certificate, ContentRevision


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def article_snapshot(article: Article) -> dict[str, Any]:
    return {
        "title": article.title,
        "content": article.content,
        "status": article.status,
        "template": article.template,
        "scheduled_publish_at": _serialize_value(article.scheduled_publish_at),
        "review_comment": article.review_comment,
    }


def certificate_snapshot(certificate: Certificate) -> dict[str, Any]:
    return {
        "name": certificate.name,
        "category": certificate.category,
        "issuer": certificate.issuer,
        "valid_from": _serialize_value(certificate.valid_from),
        "valid_to": _serialize_value(certificate.valid_to),
        "renewal_in_progress": certificate.renewal_in_progress,
        "renewal_approval_status": certificate.renewal_approval_status,
        "renewal_review_comment": certificate.renewal_review_comment,
        "responsible_name": certificate.responsible_name,
        "responsible_email": certificate.responsible_email,
        "escalate_email": certificate.escalate_email,
        "parent_id": certificate.parent_id,
        "file_asset_id": certificate.file_asset_id,
        "notes": certificate.notes,
    }


def _next_version_number(db: Session, *, entity_type: str, entity_id: str) -> int:
    current = db.scalar(
        select(func.max(ContentRevision.version_number)).where(
            ContentRevision.entity_type == entity_type,
            ContentRevision.entity_id == entity_id,
        )
    )
    return int(current or 0) + 1


def record_revision(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    snapshot: dict[str, Any],
    actor: dict,
) -> ContentRevision:
    revision = ContentRevision(
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=_next_version_number(db, entity_type=entity_type, entity_id=entity_id),
        snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        changed_by_id=actor.get("db_id") or actor.get("id", ""),
        changed_by_name=actor.get("name", ""),
    )
    db.add(revision)
    return revision


def revision_to_dict(revision: ContentRevision, *, include_snapshot: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": revision.id,
        "entity_type": revision.entity_type,
        "entity_id": revision.entity_id,
        "version_number": revision.version_number,
        "changed_by_id": revision.changed_by_id,
        "changed_by_name": revision.changed_by_name,
        "created_at": revision.created_at.isoformat(),
    }
    if include_snapshot:
        try:
            payload["snapshot"] = json.loads(revision.snapshot_json)
        except json.JSONDecodeError:
            payload["snapshot"] = {}
    return payload


def list_revisions(db: Session, *, entity_type: str, entity_id: str, limit: int = 50) -> list[dict[str, Any]]:
    revisions = db.scalars(
        select(ContentRevision)
        .where(ContentRevision.entity_type == entity_type, ContentRevision.entity_id == entity_id)
        .order_by(ContentRevision.version_number.desc())
        .limit(min(limit, 200))
    ).all()
    return [revision_to_dict(revision) for revision in revisions]


def get_revision(db: Session, revision_id: str) -> dict[str, Any]:
    revision = db.get(ContentRevision, revision_id)
    if not revision:
        raise HTTPException(status_code=404, detail="not_found")
    return revision_to_dict(revision, include_snapshot=True)


def _load_snapshot(revision: ContentRevision) -> dict[str, Any]:
    try:
        return json.loads(revision.snapshot_json)
    except json.JSONDecodeError:
        return {}


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for field in sorted(set(before) | set(after)):
        old_value = before.get(field)
        new_value = after.get(field)
        if old_value != new_value:
            changes.append({"field": field, "from": old_value, "to": new_value})
    return changes


def compare_versions(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    from_version: int,
    to_version: Optional[int] = None,
) -> dict[str, Any]:
    from_revision = db.scalar(
        select(ContentRevision).where(
            ContentRevision.entity_type == entity_type,
            ContentRevision.entity_id == entity_id,
            ContentRevision.version_number == from_version,
        )
    )
    if not from_revision:
        raise HTTPException(status_code=404, detail="not_found")

    if to_version is None:
        if entity_type == "article":
            entity = db.get(Article, entity_id)
            if not entity:
                raise HTTPException(status_code=404, detail="not_found")
            to_snapshot = article_snapshot(entity)
            to_label = "current"
        elif entity_type == "certificate":
            entity = db.get(Certificate, entity_id)
            if not entity:
                raise HTTPException(status_code=404, detail="not_found")
            to_snapshot = certificate_snapshot(entity)
            to_label = "current"
        else:
            raise HTTPException(status_code=422, detail="validation")
    else:
        to_revision = db.scalar(
            select(ContentRevision).where(
                ContentRevision.entity_type == entity_type,
                ContentRevision.entity_id == entity_id,
                ContentRevision.version_number == to_version,
            )
        )
        if not to_revision:
            raise HTTPException(status_code=404, detail="not_found")
        to_snapshot = _load_snapshot(to_revision)
        to_label = str(to_version)

    from_snapshot = _load_snapshot(from_revision)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "from_version": from_version,
        "to_version": to_label,
        "changes": diff_snapshots(from_snapshot, to_snapshot),
    }
