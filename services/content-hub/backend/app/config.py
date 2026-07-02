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
    entra_mock_auth: bool = False

    database_url: str = "sqlite:///./data/content_hub.db"
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 25 * 1024 * 1024

    supported_languages: tuple[str, ...] = ("de", "en", "zh-CN")
    default_language: str = "en"

    @property
    def entra_configured(self) -> bool:
        return bool(self.azure_tenant_id and self.azure_client_id)

    @property
    def effective_redirect_uri(self) -> str:
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if railway_domain:
            return f"https://{railway_domain}/api/auth/callback"
        return self.redirect_uri

    @property
    def effective_database_url(self) -> str:
        return normalize_database_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
