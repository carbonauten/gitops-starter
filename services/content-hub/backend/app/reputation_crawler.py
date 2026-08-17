"""Public-web reputation crawler for carbonauten GmbH / FuckCo2.

Searches public DuckDuckGo HTML and Google News RSS, including LinkedIn
``site:`` queries for carbonauten / FuckCo2 and named people (e.g. Torsten Becker).
DuckDuckGo is often blocked from datacenter IPs; Google News RSS still returns
LinkedIn sources. Uses search snippets, runs queries in parallel, and stops after
a short time budget. Does not log in, bypass paywalls, or ignore rate limits.
"""

from __future__ import annotations

import contextvars
import html as html_lib
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4
from xml.etree import ElementTree

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .database import ReputationCrawlRun, ReputationMention

logger = logging.getLogger(__name__)

USER_AGENT = "CarbonautenReputationBot/1.0 (+https://app.carbonauten.com; reputation-monitor)"
DDG_HTML = "https://html.duckduckgo.com/html/"
NEWS_RSS = "https://news.google.com/rss/search"

NEGATIVE_TERMS = (
    "betrug",
    "scam",
    "fraud",
    "kritik",
    "skandal",
    "abzocke",
    "beschwerde",
    "klage",
    "insolvenz",
    "greenwashing",
    "fake",
    "lüge",
    "luege",
    "warnung",
    "unseriös",
    "unserioes",
    "abmahnung",
    "rückruf",
    "rueckruf",
    "umweltschwindel",
    "ponzi",
    "pyramid",
    "complaint",
    "lawsuit",
    "bankrupt",
    "misleading",
    "deceptive",
)
POSITIVE_TERMS = (
    "award",
    "preis",
    "innovation",
    "nachhaltig",
    "erfolg",
    "partner",
    "auszeichnung",
    "climate",
    "biochar",
    "pflanzenkohle",
)

DEFAULT_QUERIES = (
    "carbonauten GmbH",
    "carbonauten Kritik OR Betrug OR Skandal",
    "FuckCo2 carbonauten",
)
LINKEDIN_QUERIES = (
    'site:linkedin.com "carbonauten GmbH"',
    'site:linkedin.com "carbonauten"',
    'site:linkedin.com/posts "carbonauten"',
    'site:linkedin.com/company/carbonauten',
)

MAX_QUERIES = 10
MAX_PAGE_FETCHES = 0
FETCH_TIMEOUT_SEC = 5.0
CRAWL_BUDGET_SEC = 35.0
SEARCH_WORKERS = 6

FetchFn = Callable[[str, dict[str, str] | None, dict[str, str] | None], str]
_http_client: contextvars.ContextVar[httpx.Client | None] = contextvars.ContextVar(
    "reputation_http_client",
    default=None,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _csv_terms(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def default_people(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    people = _csv_terms(getattr(settings, "reputation_people", "") or "")
    return people or ["Torsten Becker"]


def default_queries(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    seen: set[str] = set()
    queries: list[str] = []
    people_queries = [f'site:linkedin.com "{person}" carbonauten' for person in default_people(settings)]
    for item in list(DEFAULT_QUERIES) + list(LINKEDIN_QUERIES) + people_queries:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        queries.append(item)
    return queries[:MAX_QUERIES]


def is_on_brand(text: str) -> bool:
    blob = (text or "").lower()
    return "carbonauten" in blob or "fuckco2" in blob or "fuck co2" in blob


def normalize_url(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    if "duckduckgo.com" in (parsed.netloc or "") and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            value = unquote(target)
            parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return ""
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    return f"{parsed.scheme}://{host}{path}"


def source_host(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_linkedin_url(url: str) -> bool:
    host = source_host(url)
    return host in {"linkedin.com", "lnkd.in"} or host.endswith(".linkedin.com")


def detect_channel(url: str, fallback: str = "web") -> str:
    """Classify a mention URL. LinkedIn is a first-class channel."""
    if is_linkedin_url(url):
        return "linkedin"
    return fallback


def _strip_tags(markup: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", markup or "")
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def classify_sentiment(text: str) -> tuple[str, int, str]:
    blob = (text or "").lower()
    negative_hits = [term for term in NEGATIVE_TERMS if term in blob]
    positive_hits = [term for term in POSITIVE_TERMS if term in blob]
    score = len(negative_hits) * 2 - len(positive_hits)
    if score >= 2 or len(negative_hits) >= 2:
        label = "negative"
    elif score <= -2 and not negative_hits:
        label = "positive"
    elif negative_hits and not positive_hits:
        label = "negative"
        score = max(score, 2)
    else:
        label = "neutral"
    reasons = ", ".join((negative_hits + positive_hits)[:8])
    return label, score, reasons


def parse_duckduckgo_html(markup: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    pattern = re.compile(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippets = re.findall(
        r'<a[^>]*class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
        markup or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(pattern.finditer(markup or "")):
        url = normalize_url(html_lib.unescape(match.group(1)))
        title = _strip_tags(match.group(2))[:500]
        snippet = _strip_tags(snippets[index])[:800] if index < len(snippets) else ""
        if not url or not title:
            continue
        results.append({"url": url, "title": title, "snippet": snippet, "channel": detect_channel(url)})
    return results[:12]


def parse_news_rss(markup: str, *, limit: int = 12) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    try:
        root = ElementTree.fromstring(markup or "")
    except ElementTree.ParseError:
        return results
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = _strip_tags(item.findtext("description") or "")
        url = normalize_url(link)
        if not url or not title:
            continue
        source_el = item.find("source")
        source_name = (source_el.text or "").strip() if source_el is not None else ""
        source_url = (source_el.get("url") or "") if source_el is not None else ""
        if "linkedin" in source_name.lower() or "linkedin.com" in source_url.lower():
            channel = "linkedin"
        else:
            channel = detect_channel(url, fallback="news")
        results.append({
            "url": url,
            "title": title[:500],
            "snippet": description[:800],
            "channel": channel,
        })
    return results[:limit]


def default_fetch(url: str, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> str:
    merged = {"User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8"}
    if headers:
        merged.update(headers)
    shared = _http_client.get()
    if shared is not None:
        response = shared.get(url, params=params, headers=merged)
        response.raise_for_status()
        return response.text[:250_000]
    with httpx.Client(timeout=FETCH_TIMEOUT_SEC, follow_redirects=True, headers=merged) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.text[:250_000]


def search_web(query: str, *, fetch: FetchFn | None = None) -> list[dict[str, str]]:
    fetch = fetch or default_fetch
    html = fetch(DDG_HTML, {"q": query}, {"Referer": "https://html.duckduckgo.com/"})
    rows = parse_duckduckgo_html(html)
    for row in rows:
        row["query"] = query
    return rows


def search_news(query: str, *, fetch: FetchFn | None = None, limit: int = 12) -> list[dict[str, str]]:
    fetch = fetch or default_fetch
    xml = fetch(
        NEWS_RSS,
        {"q": query, "hl": "de", "gl": "DE", "ceid": "DE:de"},
        None,
    )
    rows = parse_news_rss(xml, limit=limit)
    for row in rows:
        row["query"] = query
    return rows


def fetch_excerpt(url: str, *, fetch: FetchFn | None = None) -> str:
    fetch = fetch or default_fetch
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if parsed.path.lower().endswith((".pdf", ".zip", ".jpg", ".png", ".gif", ".mp4")):
        return ""
    if is_linkedin_url(url):
        return ""
    try:
        markup = fetch(url, None, None)
    except Exception:  # noqa: BLE001
        logger.info("Could not fetch mention %s", url)
        return ""
    title = ""
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", markup)
    if match:
        title = _strip_tags(match.group(1))
    body = _strip_tags(markup)
    combined = f"{title} {body}".strip()
    return combined[:2500]


def crawl_run_to_dict(row: ReputationCrawlRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": row.status,
        "queries": int(row.queries or 0),
        "found": int(row.found or 0),
        "created": int(row.created or 0),
        "updated": int(row.updated or 0),
        "negative": int(row.negative or 0),
        "error": row.error or "",
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def mention_to_dict(row: ReputationMention, deletion: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "url": row.url,
        "title": row.title,
        "snippet": row.snippet,
        "excerpt": (row.excerpt or "")[:600],
        "source_host": row.source_host,
        "query": row.query,
        "channel": row.channel,
        "sentiment": row.sentiment,
        "sentiment_score": int(row.sentiment_score or 0),
        "sentiment_reasons": row.sentiment_reasons or "",
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "deletion": deletion,
    }
    return payload


def _upsert_mention(db: Session, payload: dict[str, str], *, excerpt: str = "") -> tuple[ReputationMention, bool]:
    url = payload["url"]
    existing = db.scalar(select(ReputationMention).where(ReputationMention.url == url))
    text = " ".join(
        part for part in (payload.get("title"), payload.get("snippet"), excerpt, payload.get("query")) if part
    )
    sentiment, score, reasons = classify_sentiment(text)
    now = _utc_now()
    channel = payload.get("channel") or "web"
    host = "linkedin.com" if channel == "linkedin" else source_host(url)
    if existing:
        existing.title = payload.get("title") or existing.title
        existing.snippet = payload.get("snippet") or existing.snippet
        if excerpt:
            existing.excerpt = excerpt
        existing.query = payload.get("query") or existing.query
        existing.channel = channel or existing.channel
        if host:
            existing.source_host = host
        existing.sentiment = sentiment
        existing.sentiment_score = score
        existing.sentiment_reasons = reasons
        existing.last_seen_at = now
        db.add(existing)
        return existing, False

    row = ReputationMention(
        id=str(uuid4()),
        url=url,
        canonical_url=url,
        title=(payload.get("title") or "")[:500],
        snippet=(payload.get("snippet") or "")[:2000],
        excerpt=excerpt[:4000],
        source_host=host,
        query=(payload.get("query") or "")[:300],
        channel=channel,
        sentiment=sentiment,
        sentiment_score=score,
        sentiment_reasons=reasons,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(row)
    return row, True


def _search_query(query: str, *, include_news: bool, fetch: FetchFn) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    linkedin_query = "linkedin" in query.lower()
    try:
        rows.extend(search_web(query, fetch=fetch))
    except Exception:  # noqa: BLE001
        logger.info("Web search failed for query %s", query)
    if include_news:
        try:
            rows.extend(search_news(query, fetch=fetch, limit=40 if linkedin_query else 12))
        except Exception:  # noqa: BLE001
            logger.info("News search failed for query %s", query)
    return [row for row in rows if is_on_brand(" ".join((row.get("title") or "", row.get("snippet") or "", query)))]


def run_reputation_crawl(
    db: Session,
    *,
    settings: Settings | None = None,
    fetch: FetchFn | None = None,
    include_news: bool = True,
    fetch_pages: bool = False,
    existing_run_id: str | None = None,
) -> ReputationCrawlRun:
    settings = settings or get_settings()
    run = db.get(ReputationCrawlRun, existing_run_id) if existing_run_id else None
    if run is None:
        run = ReputationCrawlRun(id=existing_run_id or str(uuid4()), status="running")
        db.add(run)
        db.commit()
        db.refresh(run)
    else:
        run.status = "running"
        run.error = ""
        db.add(run)
        db.commit()

    queries = default_queries(settings)
    seen_urls: set[str] = set()
    created = updated = negative = 0
    owned_client: httpx.Client | None = None
    pool: ThreadPoolExecutor | None = None
    client_token = None
    active_fetch = fetch or default_fetch
    if fetch is None:
        owned_client = httpx.Client(
            timeout=FETCH_TIMEOUT_SEC,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de,en;q=0.8"},
        )
        client_token = _http_client.set(owned_client)

    deadline = time.monotonic() + CRAWL_BUDGET_SEC
    try:
        jobs = [(query, include_news) for query in queries]
        pool = ThreadPoolExecutor(max_workers=min(SEARCH_WORKERS, max(1, len(jobs))))
        futures = {
            pool.submit(_search_query, query, include_news=news, fetch=active_fetch): query
            for query, news in jobs
        }
        remaining = max(0.1, deadline - time.monotonic())
        try:
            completed = as_completed(futures, timeout=remaining)
            for future in completed:
                if time.monotonic() >= deadline:
                    break
                try:
                    batch = future.result()
                except Exception:  # noqa: BLE001
                    logger.info("Search worker failed")
                    continue
                for item in batch:
                    url = item.get("url") or ""
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    excerpt = ""
                    if fetch_pages and MAX_PAGE_FETCHES and len(seen_urls) <= MAX_PAGE_FETCHES and not is_linkedin_url(url):
                        excerpt = fetch_excerpt(url, fetch=active_fetch)
                    _row, is_new = _upsert_mention(db, item, excerpt=excerpt)
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                    if _row.sentiment == "negative":
                        negative += 1
                run.queries = len(queries)
                run.found = len(seen_urls)
                run.created = created
                run.updated = updated
                run.negative = negative
                db.add(run)
                db.commit()
                if time.monotonic() >= deadline:
                    break
        except TimeoutError:
            logger.info("Reputation crawl reached %ss budget with %s hits", CRAWL_BUDGET_SEC, len(seen_urls))

        run.status = "ok"
        run.queries = len(queries)
        run.found = len(seen_urls)
        run.created = created
        run.updated = updated
        run.negative = negative
        run.finished_at = _utc_now()
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reputation crawl failed")
        run.status = "failed"
        run.error = str(exc)[:500]
        run.finished_at = _utc_now()
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        if client_token is not None:
            _http_client.reset(client_token)
        if owned_client is not None:
            owned_client.close()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
