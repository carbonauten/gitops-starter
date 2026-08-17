from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
import time

from sqlalchemy import select

from app.reputation_crawler import (
    classify_sentiment,
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
    search_china_press,
    search_company_china,
    search_news,
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
    assert len(queries) <= 12


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
