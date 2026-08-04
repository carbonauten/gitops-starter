"""Shop storefront page-view analytics and monitoring summaries."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import ShopPageView


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def visitor_hash(*, ip: str, user_agent: str, session_id: str) -> str:
    raw = f"{session_id.strip().lower()}|{ip}|{(user_agent or '')[:120]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def normalize_path(path: str) -> str:
    cleaned = (path or "/").strip() or "/"
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    if len(cleaned) > 1 and cleaned.endswith("/"):
        cleaned = cleaned.rstrip("/")
    return cleaned[:500]


def record_page_view(
    db: Session,
    *,
    path: str,
    referrer: str = "",
    session_id: str,
    ip: str,
    user_agent: str = "",
    customer_id: str | None = None,
) -> ShopPageView:
    view = ShopPageView(
        path=normalize_path(path),
        referrer=(referrer or "")[:500],
        session_id=(session_id or "")[:64],
        visitor_hash=visitor_hash(ip=ip, user_agent=user_agent, session_id=session_id),
        user_agent=(user_agent or "")[:300],
        customer_id=customer_id,
    )
    db.add(view)
    db.commit()
    db.refresh(view)
    return view


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def monitoring_summary(db: Session, *, days: int = 30) -> dict[str, Any]:
    days = max(1, min(int(days), 365))
    now = _utcnow()
    today = now.date()
    since = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=timezone.utc)
    since_7 = now - timedelta(days=7)
    start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

    rows = list(db.scalars(select(ShopPageView).where(ShopPageView.created_at >= since)).all())

    views_today = 0
    views_7d = 0
    unique_today: set[str] = set()
    unique_7d: set[str] = set()
    unique_period: set[str] = set()
    by_day: dict[str, int] = defaultdict(int)
    path_counts: Counter[str] = Counter()

    for row in rows:
        created = _as_utc(row.created_at) if row.created_at else now
        day_key = created.date().isoformat()
        by_day[day_key] += 1
        path_counts[row.path] += 1
        unique_period.add(row.visitor_hash)
        if created >= since_7:
            views_7d += 1
            unique_7d.add(row.visitor_hash)
        if created >= start_of_today:
            views_today += 1
            unique_today.add(row.visitor_hash)

    day_series: list[dict[str, Any]] = []
    cursor = today - timedelta(days=days - 1)
    while cursor <= today:
        key = cursor.isoformat()
        day_series.append({"day": key, "count": by_day.get(key, 0)})
        cursor += timedelta(days=1)

    recent = [
        {
            "id": row.id,
            "path": row.path,
            "referrer": row.referrer,
            "session_id": row.session_id,
            "created_at": _as_utc(row.created_at).isoformat() if row.created_at else None,
        }
        for row in db.scalars(select(ShopPageView).order_by(ShopPageView.created_at.desc()).limit(40)).all()
    ]

    return {
        "days": days,
        "views_today": views_today,
        "views_7d": views_7d,
        "views_period": len(rows),
        "unique_visitors_today": len(unique_today),
        "unique_visitors_7d": len(unique_7d),
        "unique_visitors_period": len(unique_period),
        "by_day": day_series,
        "top_paths": [{"path": path, "count": count} for path, count in path_counts.most_common(15)],
        "recent": recent,
    }
