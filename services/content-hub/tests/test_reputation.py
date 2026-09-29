from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
import base64
import contextvars
import time

from sqlalchemy import select

from app.reputation_crawler import (
    classify_sentiment,
    default_people,
    default_queries,
    detect_channel,
    extract_article_text,
    is_china_coverage,
    is_on_brand,
    mention_sentiment_text,
    news_editions_for,
    parse_duckduckgo_html,
    parse_news_rss,
    parse_wordpress_json,
    resolve_google_news_url,
    search_china_press,
    search_company_china,
    search_news,
    unwrap_google_news_url,
    _http_client,
    _resolve_pending_google_news,
    _search_query,
)


def test_http_client_contextvar_reaches_thread_pool_workers():
    """Regression test: run_reputation_crawl() sets the shared httpx.Client via
    _http_client (a contextvars.ContextVar) in the main thread, then dispatches
    fetches through a ThreadPoolExecutor. Plain ThreadPoolExecutor.submit() does
    NOT propagate contextvars into worker threads on its own — the crawl code
    must capture the context with contextvars.copy_context() and submit via
    pool.submit(ctx.run, fn, ...) so default_fetch() actually sees the shared
    client instead of opening a fresh one for every request."""
    marker = object()
    token = _http_client.set(marker)
    try:
        ctx = contextvars.copy_context()
        with ThreadPoolExecutor(max_workers=1) as pool:
            without_propagation = pool.submit(_http_client.get).result()
            with_propagation = pool.submit(ctx.run, _http_client.get).result()
        assert without_propagation is None, (
            "sanity check: plain ThreadPoolExecutor.submit() should NOT see the "
            "context var — if this fails, Python's contextvars semantics changed "
            "and the ctx.run() wrapper in run_reputation_crawl() may no longer be needed"
        )
        assert with_propagation is marker
    finally:
        _http_client.reset(token)


def test_run_reputation_crawl_reuses_shared_client(auth_client, monkeypatch):
    """End-to-end version of the regression above: a real run_reputation_crawl()
    call (fetch=None, the code path the scheduled/manual crawl actually uses)
    must only ever construct one httpx.Client, not one per HTTP request."""
    from app import reputation_crawler as rc
    from app.database import _SessionLocal

    created_clients: list[object] = []

    class FakeResponse:
        text = "<rss><channel></channel></rss>"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            created_clients.append(self)

        def get(self, *args, **kwargs) -> FakeResponse:
            return FakeResponse()

        def close(self) -> None:
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *exc_info) -> None:
            return None

    monkeypatch.setattr(rc.httpx, "Client", FakeClient)
    monkeypatch.setattr(rc, "default_queries", lambda settings=None: ["carbonauten GmbH"])

    db = _SessionLocal()
    try:
        run = rc.run_reputation_crawl(db, fetch=None, include_news=True, fetch_pages=False)
        assert run.status == "ok"
    finally:
        db.close()

    assert len(created_clients) == 1, (
        f"expected the shared client to be reused by every worker thread, "
        f"got {len(created_clients)} separate httpx.Client instances"
    )


DDG_HTML = """
<html><body>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fnews.example.com%2Fkritik">carbonauten GmbH Kritik</a>
<a class="result__snippet">Schwere Vorwürfe und Betrug-Warnung gegen carbonauten.</a>
<a class="result__a" href="https://carbonauten.com/about">Über carbonauten</a>
<a class="result__snippet">Nachhaltige Pflanzenkohle und Innovation.</a>
<a class="result__a" href="https://www.linkedin.com/posts/someone_carbonauten-activity-123">carbonauten auf LinkedIn</a>
<a class="result__snippet">Post über Carbonauten GmbH und FuckCo2.</a>
</body></html>
"""

NEWS_XML = """
<rss><channel>
<item>
  <title>Warnung: carbonauten Skandal</title>
  <link>https://blog.example.org/skandal</link>
  <description>Kritik und Beschwerde</description>
</item>
</channel></rss>
"""


def _fake_fetch(url, params=None, headers=None):
    if "duckduckgo" in url:
        return DDG_HTML
    if "news.google.com" in url:
        return NEWS_XML
    if "news.example.com" in url:
        return "<html><title>Kritik</title><body>Betrug Warnung Skandal carbonauten</body></html>"
    return "<html><title>About</title><body>Innovation nachhaltig carbonauten</body></html>"


def _wait_for_crawl(client, timeout=8.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        payload = client.get("/api/reputation/summary").json()
        last = payload.get("last_run")
        if last and last.get("status") in {"ok", "failed"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"crawl did not finish: {last}")


def test_classify_sentiment_negative_and_positive():
    label, score, reasons = classify_sentiment("carbonauten Betrug Skandal Warnung")
    assert label == "negative"
    assert score >= 2
    assert "betrug" in reasons
    pos, _, _ = classify_sentiment("carbonauten Innovation nachhaltig Preis")
    assert pos == "positive"


def test_sentiment_uses_article_body_not_search_query():
    positive = mention_sentiment_text(
        title="carbonauten Innovation nachhaltig",
        snippet="Partner und Auszeichnung",
        excerpt="Preis für Pflanzenkohle und Climate-Innovation.",
    )
    assert classify_sentiment(positive)[0] == "positive"
    poisoned = positive + " carbonauten Kritik OR Betrug OR Skandal"
    assert classify_sentiment(poisoned)[0] == "negative"

    body_negative = mention_sentiment_text(
        title="carbonauten factory update",
        snippet="A short teaser without strong words.",
        excerpt="Die Meldung wirft Betrug, Skandal und eine Klage vor. Warnung vor Greenwashing.",
    )
    assert classify_sentiment(body_negative)[0] == "negative"

    mixed_neutral = mention_sentiment_text(
        title="carbonauten in the press",
        snippet="Kurzer Hinweis.",
        excerpt="Ein Bericht ohne starke Wertung.",
    )
    assert classify_sentiment(mixed_neutral)[0] == "neutral"


def test_extract_article_text_prefers_article_body():
    markup = """
    <html><head><title>carbonauten Update</title></head>
    <body>
      <nav>Home Kritik Beschwerde</nav>
      <article><p>Die carbonauten GmbH startete den Bau in Chibi mit nachhaltiger Pflanzenkohle.</p></article>
      <footer>complaint lawsuit scam</footer>
    </body></html>
    """
    text = extract_article_text(markup)
    assert "Chibi" in text
    assert "Pflanzenkohle" in text
    assert "complaint" not in text.lower()
    assert "lawsuit" not in text.lower()


def test_parse_duckduckgo_unwraps_redirect():
    rows = parse_duckduckgo_html(DDG_HTML)
    assert rows[0]["url"] == "https://news.example.com/kritik"
    assert "Kritik" in rows[0]["title"]


def test_reputation_crawl_and_deletion_request(auth_client, monkeypatch):
    monkeypatch.setattr(
        "app.reputation_crawler.default_queries",
        lambda settings=None: ["carbonauten GmbH", "carbonauten GmbH Kritik"],
    )
    with patch("app.reputation_crawler.default_fetch", side_effect=_fake_fetch), patch(
        "app.reputation_crawler.time.sleep", return_value=None
    ), patch("app.reputation_service.send_plain_email", return_value=True) as send_email:
        crawl = auth_client.post("/api/reputation/crawl")
        assert crawl.status_code == 200
        assert crawl.json()["run"]["status"] in {"running", "ok"}
        run = _wait_for_crawl(auth_client)
        assert run["status"] == "ok"
        assert run["found"] >= 2
        assert run["negative"] >= 1

        all_mentions = auth_client.get("/api/reputation/mentions", params={"q": "linkedin"})
        assert all_mentions.status_code == 200
        linkedin_hits = [row for row in all_mentions.json()["mentions"] if row["channel"] == "linkedin"]
        assert linkedin_hits
        assert "linkedin.com" in linkedin_hits[0]["url"]

        scored = auth_client.get("/api/reputation/mentions")
        by_url = {row["url"]: row for row in scored.json()["mentions"]}
        kritik = by_url["https://news.example.com/kritik"]
        assert kritik["sentiment"] == "negative"
        assert "Betrug" in (kritik["excerpt"] or kritik["snippet"])
        about = by_url["https://carbonauten.com/about"]
        assert about["sentiment"] == "positive"
        assert "Innovation" in (about["excerpt"] or about["snippet"])

        negative = auth_client.get("/api/reputation/mentions", params={"sentiment": "negative"})
        assert negative.status_code == 200
        mentions = negative.json()["mentions"]
        assert mentions
        target = mentions[0]
        assert target["sentiment"] == "negative"
        assert target["url"].startswith("http")

        created = auth_client.post(
            f"/api/reputation/mentions/{target['id']}/deletion-requests",
            json={"reason": "inaccurate", "notes": "Unzutreffende Behauptung", "publisher_email": "redaktion@example.com"},
        )
        assert created.status_code == 201
        letter = created.json()["request"]["letter"]
        assert "carbonauten GmbH" in letter
        assert target["url"] in letter
        assert created.json()["email_sent"] is True
        assert send_email.call_count >= 1

        duplicate = auth_client.post(
            f"/api/reputation/mentions/{target['id']}/deletion-requests",
            json={"reason": "other"},
        )
        assert duplicate.status_code == 409

        summary = auth_client.get("/api/reputation/summary")
        assert summary.status_code == 200
        assert summary.json()["open_deletion_requests"] >= 1

        closed = auth_client.patch(
            f"/api/reputation/deletion-requests/{created.json()['request']['id']}/close"
        )
        assert closed.status_code == 200
        assert closed.json()["request"]["status"] == "closed"


def test_deletion_request_reports_failed_internal_email(auth_client, monkeypatch):
    """The deletion request must still be created and the DB row/audit trail must
    still reflect it, but the response has to say the internal notification failed
    instead of claiming success when send_plain_email() returns False."""
    monkeypatch.setattr(
        "app.reputation_crawler.default_queries",
        lambda settings=None: ["carbonauten GmbH"],
    )
    with patch("app.reputation_crawler.default_fetch", side_effect=_fake_fetch), patch(
        "app.reputation_crawler.time.sleep", return_value=None
    ):
        crawl = auth_client.post("/api/reputation/crawl")
        assert crawl.status_code == 200
        run = _wait_for_crawl(auth_client)
        assert run["status"] == "ok"

    mentions = auth_client.get("/api/reputation/mentions")
    target = mentions.json()["mentions"][0]

    with patch("app.reputation_service.send_plain_email", return_value=False):
        created = auth_client.post(
            f"/api/reputation/mentions/{target['id']}/deletion-requests",
            json={"reason": "other"},
        )
    assert created.status_code == 201
    assert created.json()["email_sent"] is False
    assert created.json()["request"]["status"] == "requested"


def test_reputation_forbidden_for_viewer(viewer_auth_client):
    blocked = viewer_auth_client.get("/api/reputation/mentions")
    assert blocked.status_code == 403


def test_parse_news_rss_items():
    rows = parse_news_rss(NEWS_XML)
    assert rows[0]["channel"] == "news"
    assert rows[0]["url"] == "https://blog.example.org/skandal"


def test_parse_news_rss_linkedin_source():
    xml = """
    <rss><channel>
    <item>
      <title>Torsten Becker – carbonauten - the minus CO2 factory - LinkedIn</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <description>CEO von carbonauten GmbH</description>
      <source url="https://www.linkedin.com">LinkedIn</source>
    </item>
    <item>
      <title>Unrelated Torsten Becker – lawyer</title>
      <link>https://news.google.com/rss/articles/xyz</link>
      <description>Anwaltskanzlei</description>
      <source url="https://www.linkedin.com">LinkedIn</source>
    </item>
    </channel></rss>
    """
    rows = parse_news_rss(xml, limit=20)
    assert rows[0]["channel"] == "linkedin"
    assert "Torsten Becker" in rows[0]["title"]
    assert is_on_brand(rows[0]["title"])
    assert not is_on_brand(rows[1]["title"] + " " + rows[1]["snippet"])


def test_detect_channel_linkedin():
    assert detect_channel("https://www.linkedin.com/posts/someone_carbonauten-activity-123") == "linkedin"
    assert detect_channel("https://de.linkedin.com/pulse/foo") == "linkedin"
    assert detect_channel("https://lnkd.in/abc") == "linkedin"
    assert detect_channel("https://news.example.com/story") == "web"
    assert detect_channel("https://news.example.com/story", fallback="news") == "news"


def test_parse_duckduckgo_linkedin_channel():
    html = """
    <a class="result__a" href="https://www.linkedin.com/posts/someone_carbonauten-activity-123">
      carbonauten auf LinkedIn
    </a>
    <a class="result__snippet">Post über Carbonauten GmbH</a>
    """
    rows = parse_duckduckgo_html(html)
    assert rows[0]["channel"] == "linkedin"
    assert "linkedin.com/posts" in rows[0]["url"]


def test_default_queries_include_linkedin():
    queries = default_queries()
    assert any("linkedin.com" in item for item in queries)
    assert any("Torsten Becker" in item for item in queries)
    assert any("linkedin.com/posts" in item for item in queries)
    assert any("赤壁" in item or "Chibi" in item or "中国" in item for item in queries)
    assert any("碳基科技" in item for item in queries)
    assert queries[0].startswith("site:linkedin.com/posts")
    assert len(queries) <= 20


def test_is_on_brand_matches_brand_in_linkedin_url():
    assert is_on_brand(
        "A shared update",
        "https://www.linkedin.com/posts/someone_carbonauten-activity-123",
    )
    assert not is_on_brand(
        "A shared update",
        "https://www.linkedin.com/posts/someone_unrelated-activity-123",
    )


def test_resolve_google_news_url_via_batchexecute():
    google = "https://news.google.com/rss/articles/CBMiOpaqueModernIdWithoutEmbeddedUrl"

    def fetch(url, params=None, headers=None):
        assert "news.google.com" in url
        return '<div data-n-a-sg="sig123" data-n-a-ts="1710000000"></div>'

    class FakeResponse:
        text = ')]}\'\n\n[["wrb.fr","Fbv4je","[\\"garturlres\\",\\"https://www.linkedin.com/posts/someone_carbonauten-activity-999\\",1]",null,null,null,"generic"]]'
        def raise_for_status(self):
            return None

    class FakeClient:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, data=None, headers=None):
            assert "batchexecute" in url
            assert "f.req" in (data or {})
            return FakeResponse()

    with patch("app.reputation_crawler.httpx.Client", return_value=FakeClient()):
        resolved = resolve_google_news_url(google, fetch=fetch)
    assert resolved == "https://linkedin.com/posts/someone_carbonauten-activity-999"


def test_resolve_pending_google_news_reuses_shared_client():
    """_resolve_pending_google_news() opens its own ThreadPoolExecutor (separate
    from the search-phase pool) — it needs its own contextvars.copy_context()
    capture, or resolve_google_news_url() would silently stop reusing the shared
    httpx.Client for every URL it resolves, same bug as the search phase."""
    from app.reputation_crawler import _http_client

    marker = object()
    token = _http_client.set(marker)
    seen_clients: list[object] = []
    try:
        def fake_resolve(url, *, fetch=None):
            seen_clients.append(_http_client.get())
            return url

        google_urls = [f"https://news.google.com/rss/articles/{i}" for i in range(3)]
        pending = [{"url": url, "title": "t", "snippet": "s", "channel": "linkedin"} for url in google_urls]
        with patch("app.reputation_crawler.resolve_google_news_url", side_effect=fake_resolve):
            _resolve_pending_google_news(
                pending,
                fetch=lambda *a, **k: "",
                deadline=time.monotonic() + 5,
                stats={},
            )
    finally:
        _http_client.reset(token)

    assert seen_clients, "resolve_google_news_url was never called"
    assert all(client is marker for client in seen_clients)


def test_resolve_pending_keeps_linkedin_after_unwrap():
    google = "https://news.google.com/rss/articles/CBMiOpaqueLinkedInPost"
    pending = [
        {
            "url": google,
            "title": "Team update without brand in title",
            "snippet": "Shared on LinkedIn",
            "channel": "linkedin",
            "query": 'site:linkedin.com/posts "carbonauten"',
            "pending_brand_check": "1",
            "google_news_url": google,
        }
    ]

    def resolve(url, fetch=None):
        assert url == google
        return "https://www.linkedin.com/posts/alice_carbonauten-factory-activity-1"

    stats: dict[str, int] = {}
    with patch("app.reputation_crawler.resolve_google_news_url", side_effect=resolve):
        kept = _resolve_pending_google_news(
            pending,
            fetch=lambda *a, **k: "",
            deadline=time.monotonic() + 5,
            stats=stats,
        )
    assert len(kept) == 1
    assert kept[0]["url"].endswith("alice_carbonauten-factory-activity-1")
    assert kept[0]["channel"] == "linkedin"
    assert stats.get("unwrapped_news") == 1


def test_resolve_pending_drops_offbrand_linkedin_after_unwrap():
    google = "https://news.google.com/rss/articles/CBMiOpaqueOffbrand"
    pending = [
        {
            "url": google,
            "title": "Eight Sleep mattress review",
            "snippet": "Better sleep",
            "channel": "linkedin",
            "query": 'site:linkedin.com/posts "carbonauten"',
            "pending_brand_check": "1",
        }
    ]

    def resolve(url, fetch=None):
        return "https://www.linkedin.com/posts/frank-thelen_eight-sleep-activity-1"

    stats: dict[str, int] = {}
    with patch("app.reputation_crawler.resolve_google_news_url", side_effect=resolve):
        kept = _resolve_pending_google_news(
            pending,
            fetch=lambda *a, **k: "",
            deadline=time.monotonic() + 5,
            stats=stats,
        )
    assert kept == []
    assert stats.get("linkedin_dropped") == 1


def test_search_query_defers_linkedin_google_hits_without_brand_title():
    xml = """
    <rss><channel>
    <item>
      <title>Someone – Business Development - LinkedIn</title>
      <link>https://news.google.com/rss/articles/CBMiOpaque</link>
      <description>Profile teaser</description>
      <source url="https://www.linkedin.com">LinkedIn</source>
    </item>
    </channel></rss>
    """

    def fetch(url, params=None, headers=None):
        if "duckduckgo" in url:
            raise RuntimeError("ddg blocked")
        return xml

    rows = _search_query('site:linkedin.com/posts "carbonauten"', include_news=True, fetch=fetch)
    assert len(rows) == 1
    assert rows[0].get("pending_brand_check") == "1"
    assert rows[0]["channel"] == "linkedin"


def test_default_people_uses_config(monkeypatch):
    from app.config import Settings

    settings = Settings(reputation_people="Alice Example, Bob Example")
    assert default_people(settings) == ["Alice Example", "Bob Example"]
    queries = default_queries(settings)
    assert any("Alice Example" in item for item in queries)
    assert any("Bob Example" in item for item in queries)


def test_is_on_brand_uses_configured_brand_terms(monkeypatch):
    from app.config import Settings

    settings = Settings(reputation_brand_terms="Acme Biochar,CustomBrand")
    assert is_on_brand("Acme Biochar opens plant", settings=settings)
    assert is_on_brand("CustomBrand launch", settings=settings)
    assert is_on_brand("德国碳基科技在赤壁投资", settings=settings)
    assert not is_on_brand("Unrelated Torsten Becker – lawyer", settings=settings)


def test_search_query_brand_filter_ignores_query_string():
    """Results without brand in title/snippet must be dropped even if the query has brand terms."""
    html = """
    <html><body>
    <a class="result__a" href="https://news.example.com/on-brand">carbonauten GmbH update</a>
    <a class="result__snippet">Factory news about carbonauten.</a>
    <a class="result__a" href="https://news.example.com/off-brand">Unrelated Torsten Becker – lawyer</a>
    <a class="result__snippet">Anwaltskanzlei without the company.</a>
    </body></html>
    """

    def fetch(url, params=None, headers=None):
        if "duckduckgo" in url:
            return html
        return "<rss><channel></channel></rss>"

    rows = _search_query("carbonauten Kritik OR Betrug OR Skandal", include_news=False, fetch=fetch)
    urls = {row["url"] for row in rows}
    assert "https://news.example.com/on-brand" in urls
    assert "https://news.example.com/off-brand" not in urls


def test_unwrap_google_news_url_from_article_id():
    encoded = base64.urlsafe_b64encode(b'\x08\x13"Vhttps://publisher.example.com/story/carbonauten').decode().rstrip("=")
    google = f"https://news.google.com/rss/articles/{encoded}"
    assert unwrap_google_news_url(google) == "https://publisher.example.com/story/carbonauten"


def test_unwrap_google_news_url_from_description_href():
    google = "https://news.google.com/rss/articles/CBMiOpaqueModernIdWithoutUrl"
    desc = '<a href="https://handelsblatt.example/carbonauten-chibi">lesen</a>'
    assert unwrap_google_news_url(google, description_html=desc) == "https://handelsblatt.example/carbonauten-chibi"


def test_unwrap_google_news_url_ignores_description_for_non_google_link():
    """A non-Google-News link (e.g. the company WordPress feed fallback in
    search_company_china) must never be swapped for an unrelated href found in
    its own RSS description — only Google News redirect links get unwrapped."""
    direct = "https://carbonauten.com/blog/chibi-baustart"
    desc = '<a href="https://carbonauten.com/tag/china">Mehr zu China</a>'
    assert unwrap_google_news_url(direct, description_html=desc) == direct


def test_parse_news_rss_unwraps_google_article_link():
    encoded = base64.urlsafe_b64encode(b'\x08\x13"Rhttps://blog.example.org/skandal-carbonauten').decode().rstrip("=")
    xml = f"""
    <rss><channel>
    <item>
      <title>Warnung: carbonauten Skandal</title>
      <link>https://news.google.com/rss/articles/{encoded}</link>
      <description>Kritik und Beschwerde</description>
    </item>
    </channel></rss>
    """
    rows = parse_news_rss(xml)
    assert rows[0]["url"] == "https://blog.example.org/skandal-carbonauten"
    assert rows[0]["google_news_url"].startswith("https://news.google.com/")
    assert rows[0]["channel"] == "news"


def test_news_editions_cover_china():
    china = news_editions_for("carbonauten 中国 OR Chibi")
    assert any(item["hl"].startswith("zh") for item in china)
    assert any(item["gl"] == "HK" for item in china)
    linkedin = news_editions_for('site:linkedin.com "carbonauten"')
    assert len(linkedin) == 1
    assert linkedin[0]["gl"] == "DE"


def test_search_news_queries_multiple_editions():
    seen_ceid = []

    def fetch(url, params=None, headers=None):
        seen_ceid.append((params or {}).get("ceid"))
        return NEWS_XML

    rows = search_news("carbonauten 赤壁", fetch=fetch, editions=None)
    assert rows
    assert "DE:de" in seen_ceid
    assert "US:zh-Hans" in seen_ceid


def test_is_on_brand_accepts_chinese_trade_name_and_company_site():
    assert is_on_brand("德国碳基科技在赤壁投资")
    assert is_on_brand("Bau der minus CO2 factory 002 in Chibi gestartet", "https://carbonauten.com/unkategorisiert/bau-der-minus-co2-factory-002-in-chibi-gestartet/")
    assert not is_on_brand("Unrelated Torsten Becker – lawyer")


def test_is_china_coverage():
    assert is_china_coverage("Construction of minus CO2 factory 002 begins in Chibi, China")
    assert is_china_coverage("德国碳基科技在赤壁投资15亿欧元")
    assert not is_china_coverage("CO2-negative parts for the ICE")


def test_parse_wordpress_json_chibi_post():
    payload = """
    [{"link":"https://carbonauten.com/unkategorisiert/bau-der-minus-co2-factory-002-in-chibi-gestartet/",
      "title":{"rendered":"Bau der minus CO2 factory 002 in Chibi gestartet"},
      "excerpt":{"rendered":"<p>Die carbonauten GmbH startete den Bau in Chibi.</p>"},
      "content":{"rendered":"<p>Die carbonauten GmbH startete den Bau der weltweit größten Anlage in Chibi. Nachhaltig und Innovation.</p>"}}]
    """
    rows = parse_wordpress_json(payload)
    assert rows[0]["url"].endswith("/bau-der-minus-co2-factory-002-in-chibi-gestartet/")
    assert "Chibi" in rows[0]["title"]
    assert "weltweit" in rows[0]["excerpt"]
    assert rows[0]["channel"] == "web"


def test_search_company_china_uses_wordpress_then_feed(monkeypatch):
    wp = """
    [{"link":"https://carbonauten.com/en/unkategorisiert/construction-of-minus-co2-factory-002-begins-in-chibi-china/",
      "title":{"rendered":"Construction of minus CO2 factory 002 begins in Chibi, China"},
      "excerpt":{"rendered":"<p>carbonauten GmbH started construction in Hubei.</p>"}}]
    """
    ice = """
    [{"link":"https://carbonauten.com/fuck-co2/ice/",
      "title":{"rendered":"CO2-negative parts for the ICE"},
      "excerpt":{"rendered":"<p>carbonauten seat shells</p>"}}]
    """

    def fetch(url, params=None, headers=None):
        if "wp-json" in url:
            return wp if (params or {}).get("search") == "Chibi" else ice
        raise AssertionError("feed should not be used when WP search returns hits")

    rows = search_company_china(fetch=fetch)
    urls = {row["url"] for row in rows}
    assert any("chibi-china" in url for url in urls)
    assert not any("/ice/" in url for url in urls)


def test_search_company_china_falls_back_to_feed():
    feed = """
    <rss><channel>
    <item>
      <title>Bau der minus CO2 factory 002 in Chibi gestartet</title>
      <link>https://carbonauten.com/unkategorisiert/bau-der-minus-co2-factory-002-in-chibi-gestartet/</link>
      <description>Die carbonauten GmbH startete den Bau in Chibi.</description>
    </item>
    <item>
      <title>CO2-negative Teile für den ICE</title>
      <link>https://carbonauten.com/fuck-co2/ice/</link>
      <description>carbonauten Sitzschalen</description>
    </item>
    </channel></rss>
    """

    def fetch(url, params=None, headers=None):
        if "wp-json" in url:
            return "not-json"
        if url.endswith("/feed/") or url.endswith("/en/feed/"):
            return feed
        raise AssertionError(url)

    rows = search_company_china(fetch=fetch)
    assert any("chibi" in row["url"] for row in rows)
    assert not any("/ice/" in row["url"] for row in rows)


def test_search_china_press_keeps_chibi_articles_only():
    pages = {
        "https://360powder.com/info_details/index/10911.html": (
            "<html><title>德国carbonauten公司负碳材料中国总部基地项目开工</title>"
            "<body>11月7日赤壁开工 carbonauten</body></html>"
        ),
        "https://hb.cri.cn/chinanews/20230803/f9823a7b-46a1-a3f0-70aa-bf3a57d75918.html": (
            "<html><title>德国碳基科技在赤壁投资15亿欧元</title><body>湖北日报 赤壁</body></html>"
        ),
        "http://zhonglingj.com/index.php/en/industrytrends/1261.html": (
            "<html><title>Unrelated factory news</title><body>No brand here</body></html>"
        ),
        "http://dacaijing.cc/dacaijing/39905.html": (
            "<html><title>About</title><body>Innovation nachhaltig carbonauten</body></html>"
        ),
    }

    def fetch(url, params=None, headers=None):
        return pages[url]

    rows = search_china_press(fetch=fetch)
    urls = {row["url"] for row in rows}
    assert "https://360powder.com/info_details/index/10911.html" in urls
    assert "https://hb.cri.cn/chinanews/20230803/f9823a7b-46a1-a3f0-70aa-bf3a57d75918.html" in urls
    assert "http://zhonglingj.com/index.php/en/industrytrends/1261.html" not in urls
    assert "http://dacaijing.cc/dacaijing/39905.html" not in urls


def test_reputation_mentions_optional_date_range(auth_client, monkeypatch):
    from app.config import get_settings
    from app.database import ReputationMention, _SessionLocal, init_database

    monkeypatch.setattr(
        "app.reputation_crawler.default_queries",
        lambda settings=None: ["carbonauten GmbH"],
    )
    with patch("app.reputation_crawler.default_fetch", side_effect=_fake_fetch), patch(
        "app.reputation_crawler.time.sleep", return_value=None
    ):
        crawl = auth_client.post("/api/reputation/crawl")
        assert crawl.status_code == 200
        run = _wait_for_crawl(auth_client)
        assert run["status"] == "ok"

    if _SessionLocal is None:
        init_database(get_settings().effective_database_url)
    from app.database import _SessionLocal as session_factory

    db = session_factory()
    try:
        rows = list(db.scalars(select(ReputationMention)).all())
        assert rows
        old = rows[0]
        old.last_seen_at = datetime.now(timezone.utc) - timedelta(days=40)
        old_url = old.url
        db.add(old)
        db.commit()
    finally:
        db.close()

    today = date.today()
    recent = auth_client.get(
        "/api/reputation/mentions",
        params={"seen_from": (today - timedelta(days=7)).isoformat()},
    )
    assert recent.status_code == 200
    recent_urls = {row["url"] for row in recent.json()["mentions"]}
    assert old_url not in recent_urls

    unfiltered = auth_client.get("/api/reputation/mentions")
    assert old_url in {row["url"] for row in unfiltered.json()["mentions"]}

    past = auth_client.get(
        "/api/reputation/mentions",
        params={
            "seen_from": (today - timedelta(days=50)).isoformat(),
            "seen_to": (today - timedelta(days=30)).isoformat(),
        },
    )
    assert past.status_code == 200
    past_urls = {row["url"] for row in past.json()["mentions"]}
    assert old_url in past_urls

    future = auth_client.get(
        "/api/reputation/mentions",
        params={"seen_from": (today + timedelta(days=2)).isoformat()},
    )
    assert future.json()["mentions"] == []


def test_reputation_crawl_returns_before_work_finishes(auth_client, monkeypatch):
    def slow_fetch(url, params=None, headers=None):
        time.sleep(0.4)
        return _fake_fetch(url, params, headers)

    monkeypatch.setattr(
        "app.reputation_crawler.default_queries",
        lambda settings=None: ["carbonauten GmbH"],
    )
    with patch("app.reputation_crawler.default_fetch", side_effect=slow_fetch), patch(
        "app.reputation_crawler.time.sleep", return_value=None
    ):
        started = time.time()
        crawl = auth_client.post("/api/reputation/crawl")
        elapsed = time.time() - started
        assert crawl.status_code == 200
        assert elapsed < 1.0
        assert crawl.json()["run"]["status"] in {"running", "ok"}
        run = _wait_for_crawl(auth_client, timeout=12)
        assert run["status"] == "ok"
        assert run["found"] >= 1


def test_stale_running_crawl_is_marked_failed(auth_client):
    from app.config import get_settings
    from app.database import ReputationCrawlRun, _SessionLocal, init_database

    if _SessionLocal is None:
        init_database(get_settings().effective_database_url)
    from app.database import _SessionLocal as session_factory

    db = session_factory()
    try:
        db.add(
            ReputationCrawlRun(
                id="stale-reputation-run",
                status="running",
                started_at=datetime.now(timezone.utc) - timedelta(minutes=20),
            )
        )
        db.commit()
    finally:
        db.close()

    summary = auth_client.get("/api/reputation/summary")
    assert summary.status_code == 200
    last_run = summary.json()["last_run"]
    assert last_run["status"] == "failed"
    assert last_run["error"] == "timed_out"
