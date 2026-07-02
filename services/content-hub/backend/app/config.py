from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def ensure_postgres_ssl(url: str) -> str:
    """Railway Postgres uses TLS with a self-signed cert; require SSL without verify."""
    if not url or url.startswith("sqlite"):
        return url
    if "sslmode=" in url.lower():
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}sslmode=require"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Unified Carbonauten Platform"
    port: int = 8080
    session_secret: str = "dev-only-change-in-production"
    session_max_age: int = 60 * 60 * 24 * 7

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    redirect_uri: str = "http://localhost:8080/api/auth/callback"
    app_public_url: str = ""
    entra_mock_auth: bool = False
    mock_user_email: str = "demo@example.com"
    mock_user_name: str = "Demo User"
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    initial_admin_name: str = ""
    it_admin_emails: str = ""
    default_user_role: str = "editor"
    allow_self_registration: bool = True

    database_url: str = "sqlite:///./data/content_hub.db"
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 25 * 1024 * 1024

    supported_languages: tuple[str, ...] = ("de", "en", "zh-CN")
    default_language: str = "en"

    @property
    def entra_configured(self) -> bool:
        return bool(self.azure_tenant_id and self.azure_client_id and self.azure_client_secret)

    @property
    def it_admin_emails_list(self) -> set[str]:
        return {email.strip().lower() for email in self.it_admin_emails.split(",") if email.strip()}

    @property
    def effective_public_origin(self) -> str:
        if self.app_public_url.strip():
            return self.app_public_url.strip().rstrip("/")
        explicit = self.redirect_uri.strip()
        if explicit.startswith("https://") and "/api/auth/callback" in explicit:
            return explicit.split("/api/auth/callback", 1)[0]
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if railway_domain:
            return f"https://{railway_domain}"
        if explicit.startswith("http"):
            return explicit.split("/api/auth/callback", 1)[0]
        return ""

    @property
    def effective_redirect_uri(self) -> str:
        if self.app_public_url.strip():
            return f"{self.app_public_url.strip().rstrip('/')}/api/auth/callback"
        explicit = self.redirect_uri.strip()
        if explicit and "localhost" not in explicit:
            return explicit
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if railway_domain:
            return f"https://{railway_domain}/api/auth/callback"
        return explicit or "http://localhost:8080/api/auth/callback"

    @property
    def cookie_secure(self) -> bool:
        override = os.getenv("COOKIE_SECURE", "").strip().lower()
        if override == "false":
            return False
        if override == "true":
            return True
        return self.effective_public_origin.startswith("https://")

    @property
    def effective_database_url(self) -> str:
        url = (self.database_url or "").strip()
        if not url:
            url = "sqlite:///./data/content_hub.db"
        return ensure_postgres_ssl(normalize_database_url(url))


@lru_cache
def get_settings() -> Settings:
    return Settings()
