from app.config import ensure_postgres_ssl, normalize_database_url


def test_normalize_database_url_for_railway():
    raw = "postgres://user:pass@host:5432/railway"
    assert normalize_database_url(raw) == "postgresql+psycopg2://user:pass@host:5432/railway"

    pg = "postgresql://user:pass@host:5432/railway"
    assert normalize_database_url(pg) == "postgresql+psycopg2://user:pass@host:5432/railway"

    sqlite = "sqlite:///./data/content_hub.db"
    assert normalize_database_url(sqlite) == sqlite


def test_ensure_postgres_ssl_for_railway():
    url = "postgresql+psycopg2://user:pass@postgres.railway.internal:5432/railway"
    assert ensure_postgres_ssl(url) == f"{url}?sslmode=require"

    with_ssl = f"{url}?sslmode=disable"
    assert ensure_postgres_ssl(with_ssl) == with_ssl

    sqlite = "sqlite:///./data/content_hub.db"
    assert ensure_postgres_ssl(sqlite) == sqlite
