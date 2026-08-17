from unittest.mock import patch

from app.reputation_crawler import (
    classify_sentiment,
    default_queries,
    detect_channel,
    parse_duckduckgo_html,
    parse_news_rss,
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


def test_classify_sentiment_negative_and_positive():
    label, score, reasons = classify_sentiment("carbonauten Betrug Skandal Warnung")
    assert label == "negative"
    assert score >= 2
    assert "betrug" in reasons
    pos, _, _ = classify_sentiment("carbonauten Innovation nachhaltig Preis")
    assert pos == "positive"


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
        run = crawl.json()["run"]
        assert run["status"] == "ok"
        assert run["found"] >= 2
        assert run["negative"] >= 1

        all_mentions = auth_client.get("/api/reputation/mentions", params={"q": "linkedin"})
        assert all_mentions.status_code == 200
        linkedin_hits = [row for row in all_mentions.json()["mentions"] if row["channel"] == "linkedin"]
        assert linkedin_hits
        assert "linkedin.com" in linkedin_hits[0]["url"]

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


def test_detect_channel_linkedin():
    assert detect_channel("https://www.linkedin.com/posts/someone_carbonauten-activity-123") == "linkedin"
    assert detect_channel("https://de.linkedin.com/pulse/foo") == "linkedin"
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
    assert any("linkedin.com/posts" in item for item in queries)
