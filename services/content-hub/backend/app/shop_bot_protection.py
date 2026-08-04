"""Shop bot protection: rate limits, honeypot, optional Cloudflare Turnstile."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, Request

from .config import get_settings

logger = logging.getLogger(__name__)

# bucket -> timestamps of recent hits
_hits: dict[str, Deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, *, bucket: str, limit: int, window_seconds: int) -> None:
    """Raise 429 when the client exceeds `limit` hits within `window_seconds` for `bucket`."""
    settings = get_settings()
    if not settings.shop_bot_protection_enabled:
        return
    if limit <= 0 or window_seconds <= 0:
        return

    ip = client_ip(request)
    key = f"{bucket}:{ip}"
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        queue = _hits[key]
        while queue and queue[0] < cutoff:
            queue.popleft()
        if len(queue) >= limit:
            raise HTTPException(status_code=429, detail="rate_limited")
        queue.append(now)
        # Bound memory for idle keys
        if len(_hits) > 10_000:
            stale = [k for k, q in _hits.items() if not q or q[-1] < cutoff]
            for k in stale[:2000]:
                _hits.pop(k, None)


def reject_if_honeypot(value: str | None) -> None:
    """Bots often fill hidden fields; humans leave them empty."""
    if value and str(value).strip():
        raise HTTPException(status_code=400, detail="bot_detected")


def verify_turnstile(token: str | None, request: Request) -> None:
    """When Turnstile secret is configured, require a valid response token."""
    settings = get_settings()
    secret = settings.shop_turnstile_secret_key.strip()
    if not secret:
        return
    if not (token or "").strip():
        raise HTTPException(status_code=400, detail="captcha_required")

    data = urllib.parse.urlencode(
        {
            "secret": secret,
            "response": token.strip(),
            "remoteip": client_ip(request),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Turnstile verify failed: %s", exc)
        raise HTTPException(status_code=503, detail="captcha_unavailable") from exc

    if not payload.get("success"):
        raise HTTPException(status_code=400, detail="captcha_failed")


def protect_shop_action(
    request: Request,
    *,
    bucket: str,
    honeypot: str | None = None,
    turnstile_token: str | None = None,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> None:
    settings = get_settings()
    reject_if_honeypot(honeypot)
    enforce_rate_limit(
        request,
        bucket=bucket,
        limit=limit if limit is not None else settings.shop_bot_rate_limit,
        window_seconds=window_seconds if window_seconds is not None else settings.shop_bot_rate_window_seconds,
    )
    verify_turnstile(turnstile_token, request)


def reset_rate_limits_for_tests() -> None:
    with _lock:
        _hits.clear()
