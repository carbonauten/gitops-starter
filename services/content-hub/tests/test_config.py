from app.config import normalize_database_url


def test_normalize_database_url_for_railway():
    raw = "postgres://user:pass@host:5432/railway"
    assert normalize_database_url(raw) == "postgresql+psycopg2://user:pass@host:5432/railway"

    pg = "postgresql://user:pass@host:5432/railway"
    assert normalize_database_url(pg) == "postgresql+psycopg2://user:pass@host:5432/railway"

    sqlite = "sqlite:///./data/content_hub.db"
    assert normalize_database_url(sqlite) == sqlite
