from __future__ import annotations

from datetime import date, timedelta


def compute_certificate_status(valid_to: date, renewal_in_progress: bool, today: date | None = None) -> str:
    today = today or date.today()
    if renewal_in_progress:
        return "renewal"
    if valid_to < today:
        return "expired"
    if (valid_to - today).days <= 30:
        return "expiring"
    return "valid"


def days_until_expiry(valid_to: date, today: date | None = None) -> int:
    today = today or date.today()
    return (valid_to - today).days


def expiry_window_end(days: int, today: date | None = None) -> date:
    today = today or date.today()
    return today + timedelta(days=days)
