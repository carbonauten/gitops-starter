"""Reputation mentions, crawl runs, and deletion-request workflow."""

from __future__ import annotations

import logging
import threading
import time as time_mod
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit_service import log_audit
from .config import get_settings
from .database import ReputationCrawlRun, ReputationDeletionRequest, ReputationMention
from .email_service import send_plain_email
from .reputation_crawler import crawl_run_to_dict, run_reputation_crawl, source_host

logger = logging.getLogger(__name__)

DELETION_REASONS = {"gdpr", "inaccurate", "defamation", "other"}
STALE_RUNNING_MINUTES = 3
_start_lock = threading.Lock()
_worker_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_start(value: date) -> datetime:
    return datetime.combine(value, dt_time.min, tzinfo=timezone.utc)


def _day_end(value: date) -> datetime:
    return datetime.combine(value, dt_time.max, tzinfo=timezone.utc)


def expire_stale_runs(db: Session) -> int:
    cutoff = _utc_now() - timedelta(minutes=STALE_RUNNING_MINUTES)
    rows = list(
        db.scalars(
            select(ReputationCrawlRun).where(
                ReputationCrawlRun.status == "running",
                ReputationCrawlRun.started_at < cutoff,
            )
        ).all()
    )
    now = _utc_now()
    for row in rows:
        row.status = "failed"
        row.error = "timed_out"
        row.finished_at = now
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def get_running_run(db: Session) -> ReputationCrawlRun | None:
    return db.scalar(
        select(ReputationCrawlRun)
        .where(ReputationCrawlRun.status == "running")
        .order_by(ReputationCrawlRun.started_at.desc())
        .limit(1)
    )


def _crawl_worker(run_id: str) -> None:
    from .database import _SessionLocal

    if not _worker_lock.acquire(blocking=False):
        return
    try:
        if _SessionLocal is None:
            return
        db = _SessionLocal()
        try:
            run_reputation_crawl(db, existing_run_id=run_id)
        except Exception:  # noqa: BLE001
            logger.exception("Background reputation crawl failed")
            run = db.get(ReputationCrawlRun, run_id)
            if run and run.status == "running":
                run.status = "failed"
                run.error = "worker_failed"
                run.finished_at = _utc_now()
                db.add(run)
                db.commit()
        finally:
            db.close()
    finally:
        _worker_lock.release()


def guess_publisher_email(url: str) -> str:
    host = source_host(url)
    if not host or host.endswith("google.com") or host.endswith("duckduckgo.com"):
        return ""
    return f"datenschutz@{host}"


def build_deletion_letter(mention: ReputationMention, *, reason: str, notes: str, actor_name: str) -> str:
    reason_label = {
        "gdpr": "Löschung personenbezogener Daten (Art. 17 DSGVO)",
        "inaccurate": "Berichtigung / Löschung unzutreffender Angaben",
        "defamation": "Entfernung rufschädigender Inhalte",
        "other": "Löschung / Entfernung der Veröffentlichung",
    }.get(reason, "Löschung")
    return (
        f"Betreff: Löschungsersuchen — {mention.title or mention.url}\n\n"
        f"Sehr geehrte Damen und Herren,\n\n"
        f"wir schreiben im Namen der carbonauten GmbH ({actor_name}).\n"
        f"Auf Ihrer Website ist folgender Inhalt über uns veröffentlicht:\n\n"
        f"Titel: {mention.title or '—'}\n"
        f"URL: {mention.url}\n\n"
        f"Wir beantragen: {reason_label}.\n"
        f"{('Begründung: ' + notes.strip() + chr(10)) if notes.strip() else ''}\n"
        f"Bitte entfernen Sie den Beitrag oder antworten Sie uns mit einer Stellungnahme "
        f"innerhalb von 14 Tagen.\n\n"
        f"Mit freundlichen Grüßen\n"
        f"{actor_name}\n"
        f"carbonauten GmbH\n"
        f"https://app.carbonauten.com\n"
    )


def latest_deletion_map(db: Session, mention_ids: list[str]) -> dict[str, ReputationDeletionRequest]:
    if not mention_ids:
        return {}
    rows = list(
        db.scalars(
            select(ReputationDeletionRequest)
            .where(ReputationDeletionRequest.mention_id.in_(mention_ids))
            .order_by(ReputationDeletionRequest.created_at.desc())
        ).all()
    )
    latest: dict[str, ReputationDeletionRequest] = {}
    for row in rows:
        if row.mention_id not in latest:
            latest[row.mention_id] = row
    return latest


def deletion_to_dict(row: ReputationDeletionRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "mention_id": row.mention_id,
        "status": row.status,
        "reason": row.reason,
        "notes": row.notes,
        "letter": row.letter,
        "publisher_email": row.publisher_email,
        "requested_by_name": row.requested_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_mentions(
    db: Session,
    *,
    sentiment: Optional[str] = None,
    query: Optional[str] = None,
    seen_from: Optional[date] = None,
    seen_to: Optional[date] = None,
    limit: int = 100,
) -> list[tuple[ReputationMention, ReputationDeletionRequest | None]]:
    stmt = select(ReputationMention).order_by(
        ReputationMention.sentiment_score.desc(),
        ReputationMention.last_seen_at.desc(),
    )
    if sentiment:
        stmt = stmt.where(ReputationMention.sentiment == sentiment)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            (ReputationMention.title.ilike(like))
            | (ReputationMention.snippet.ilike(like))
            | (ReputationMention.source_host.ilike(like))
            | (ReputationMention.url.ilike(like))
        )
    start = _day_start(seen_from) if seen_from else None
    end = _day_end(seen_to) if seen_to else None
    if start and end and start > end:
        start, end = _day_start(seen_to), _day_end(seen_from)
    if start:
        stmt = stmt.where(ReputationMention.last_seen_at >= start)
    if end:
        stmt = stmt.where(ReputationMention.last_seen_at <= end)
    rows = list(db.scalars(stmt.limit(max(1, min(limit, 200)))).all())
    deletions = latest_deletion_map(db, [row.id for row in rows])
    return [(row, deletions.get(row.id)) for row in rows]


def summary(db: Session) -> dict[str, Any]:
    expire_stale_runs(db)
    total = db.scalar(select(func.count()).select_from(ReputationMention)) or 0
    negative = (
        db.scalar(select(func.count()).select_from(ReputationMention).where(ReputationMention.sentiment == "negative"))
        or 0
    )
    positive = (
        db.scalar(select(func.count()).select_from(ReputationMention).where(ReputationMention.sentiment == "positive"))
        or 0
    )
    open_requests = (
        db.scalar(
            select(func.count())
            .select_from(ReputationDeletionRequest)
            .where(ReputationDeletionRequest.status.in_(("requested", "sent")))
        )
        or 0
    )
    last_run = db.scalar(select(ReputationCrawlRun).order_by(ReputationCrawlRun.started_at.desc()).limit(1))
    return {
        "total": int(total),
        "negative": int(negative),
        "positive": int(positive),
        "neutral": int(total) - int(negative) - int(positive),
        "open_deletion_requests": int(open_requests),
        "last_run": crawl_run_to_dict(last_run) if last_run else None,
    }


def start_crawl(db: Session, *, actor: dict[str, Any] | None = None, wait: bool = False) -> ReputationCrawlRun:
    expire_stale_runs(db)
    with _start_lock:
        active = get_running_run(db)
        worker_busy = _worker_lock.locked()
        if active and worker_busy:
            run_id = active.id
            created = False
        elif active and not worker_busy:
            run_id = active.id
            created = True
        else:
            run = ReputationCrawlRun(id=str(uuid4()), status="running")
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
            created = True
            if actor:
                log_audit(
                    db,
                    entity_type="reputation_crawl",
                    entity_id=run.id,
                    action="crawl",
                    actor=actor,
                    details={"status": "running"},
                )

    if not created:
        if wait:
            deadline = time_mod.time() + 90
            while time_mod.time() < deadline:
                db.expire_all()
                current = db.get(ReputationCrawlRun, run_id)
                if current and current.status != "running":
                    return current
                time_mod.sleep(0.05)
        current = db.get(ReputationCrawlRun, run_id)
        if current:
            return current
        raise RuntimeError("reputation_crawl_missing")

    if wait:
        _crawl_worker(run_id)
        db.expire_all()
        finished = db.get(ReputationCrawlRun, run_id)
        if finished:
            return finished
        raise RuntimeError("reputation_crawl_missing")

    threading.Thread(target=_crawl_worker, args=(run_id,), daemon=True, name="reputation-crawl").start()
    started = db.get(ReputationCrawlRun, run_id)
    if started:
        return started
    raise RuntimeError("reputation_crawl_missing")


def request_deletion(
    db: Session,
    mention: ReputationMention,
    *,
    reason: str,
    notes: str = "",
    publisher_email: str = "",
    actor: dict[str, Any] | None = None,
) -> ReputationDeletionRequest:
    cleaned_reason = (reason or "other").strip().lower()
    if cleaned_reason not in DELETION_REASONS:
        cleaned_reason = "other"
    actor = actor or {}
    actor_name = actor.get("name") or "carbonauten GmbH"
    email = (publisher_email or "").strip() or guess_publisher_email(mention.url)
    letter = build_deletion_letter(mention, reason=cleaned_reason, notes=notes, actor_name=actor_name)
    existing = db.scalar(
        select(ReputationDeletionRequest)
        .where(
            ReputationDeletionRequest.mention_id == mention.id,
            ReputationDeletionRequest.status.in_(("requested", "sent")),
        )
        .order_by(ReputationDeletionRequest.created_at.desc())
        .limit(1)
    )
    if existing:
        raise HTTPException(status_code=409, detail="deletion_already_open")

    row = ReputationDeletionRequest(
        id=str(uuid4()),
        mention_id=mention.id,
        status="requested",
        reason=cleaned_reason,
        notes=(notes or "").strip()[:4000],
        letter=letter,
        publisher_email=email[:200],
        requested_by_id=actor.get("id") or "",
        requested_by_name=actor_name,
        requested_by_email=actor.get("email") or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    settings = get_settings()
    inbox = settings.shop_contact
    body = (
        f"Löschantrag {row.id}\n"
        f"URL: {mention.url}\n"
        f"Titel: {mention.title}\n"
        f"Sentiment: {mention.sentiment}\n"
        f"Empfänger-Vorschlag: {row.publisher_email or '—'}\n\n"
        f"{letter}\n"
    )
    send_plain_email(
        to_email=inbox,
        subject=f"Löschantrag Web-Reputation: {mention.source_host or mention.url}",
        body=body,
        settings=settings,
    )
    log_audit(
        db,
        entity_type="reputation_deletion",
        entity_id=row.id,
        action="request",
        actor=actor,
        details={"mention_id": mention.id, "url": mention.url, "reason": cleaned_reason},
    )
    return row


def close_deletion(db: Session, row: ReputationDeletionRequest, *, actor: dict[str, Any] | None = None) -> ReputationDeletionRequest:
    row.status = "closed"
    row.updated_at = _utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    if actor:
        log_audit(
            db,
            entity_type="reputation_deletion",
            entity_id=row.id,
            action="close",
            actor=actor,
            details={"mention_id": row.mention_id},
        )
    return row
