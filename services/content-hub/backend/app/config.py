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
    invite_expiry_days: int = 7

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = ""
    smtp_use_tls: bool = True
    resend_api_key: str = ""

    notion_api_key: str = ""
    notion_database_id: str = ""
    notion_client_id: str = ""
    notion_client_secret: str = ""
    teams_team_id: str = ""
    teams_channel_id: str = ""
    outlook_sender_id: str = ""
    publish_mock_mode: bool = True
    files_browse_mock_mode: bool = True
    sharepoint_site_url: str = ""
    sharepoint_drive_id: str = ""
    sharepoint_display_name: str = "SharePoint"

    shop_hosts: str = "fuckco2.shop,www.fuckco2.shop"
    shop_brand_name: str = "FuckCo2"
    shop_company_name: str = "carbonauten GmbH"
    shop_tagline: str = "FuckCo2 goes international"
    shop_contact_email: str = ""
    shop_currency: str = "EUR"
    shop_shipping_cents: int = 0
    shop_free_shipping_from_cents: int = 0
    shop_stripe_secret_key: str = ""
    shop_stripe_webhook_secret: str = ""
    shop_stripe_publishable_key: str = ""
    shop_success_path: str = "/order/success"
    shop_cancel_path: str = "/cart"
    shop_impressum: str = ""
    shop_privacy: str = ""
    shop_terms: str = ""
    shop_bank_iban: str = ""
    shop_bank_bic: str = ""
    shop_bank_name: str = ""
    shop_bank_holder: str = ""
    # Optional shop master account (defaults to INITIAL_ADMIN_*)
    shop_admin_email: str = ""
    shop_admin_password: str = ""
    shop_admin_name: str = ""
    # CO2 Reward Credits: credits awarded per full euro of paid order total
    shop_co2_credits_per_euro: int = 1
    shop_require_account_checkout: bool = False
    shop_return_window_days: int = 30
    # Bot protection (rate limit + honeypot; optional Cloudflare Turnstile)
    shop_bot_protection_enabled: bool = True
    shop_bot_rate_limit: int = 30
    shop_bot_rate_window_seconds: int = 60
    shop_bot_auth_rate_limit: int = 12
    shop_bot_checkout_rate_limit: int = 10
    shop_bot_pageview_rate_limit: int = 120
    shop_turnstile_site_key: str = ""
    shop_turnstile_secret_key: str = ""
    shop_analytics_enabled: bool = True

    # CA Auto-Import (SSL / Let's Encrypt / Azure Key Vault)
    letsencrypt_live_dir: str = ""
    azure_key_vault_url: str = ""
    key_vault_mock_mode: bool = False

    database_url: str = "sqlite:///./data/content_hub.db"
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 25 * 1024 * 1024

    deployment_region: str = "eu"
    storage_backend: str = "local"
    oss_endpoint: str = ""
    oss_bucket: str = ""
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_object_prefix: str = "uploads"

    sync_peer_url: str = ""
    sync_peer_region: str = "cn"
    sync_api_key: str = ""

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    reputation_crawl_enabled: bool = True
    reputation_crawl_interval_hours: int = 6
    reputation_brand_terms: str = "carbonauten GmbH,carbonauten,FuckCo2,fuckco2"

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
    def effective_from_email(self) -> str:
        return self.smtp_from_email.strip()

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.effective_from_email)

    @property
    def resend_configured(self) -> bool:
        return bool(self.resend_api_key.strip() and self.effective_from_email)

    @property
    def email_delivery_configured(self) -> bool:
        return self.resend_configured or self.smtp_configured

    @property
    def email_provider(self) -> str:
        if self.resend_configured:
            return "resend"
        if self.smtp_configured:
            return "smtp"
        return "none"

    @property
    def invite_base_url(self) -> str:
        origin = self.effective_public_origin
        if origin:
            return origin
        return "http://localhost:8080"

    @property
    def notion_configured(self) -> bool:
        return bool(self.notion_api_key.strip() and self.notion_database_id.strip())

    @property
    def notion_oauth_configured(self) -> bool:
        return bool(self.notion_client_id.strip() and self.notion_client_secret.strip())

    @property
    def graph_publish_configured(self) -> bool:
        return self.entra_configured

    @property
    def sharepoint_configured(self) -> bool:
        return bool(self.sharepoint_site_url.strip() or self.sharepoint_drive_id.strip())

    @property
    def files_sources_configured(self) -> bool:
        return self.sharepoint_configured or self.graph_publish_configured

    @property
    def oss_configured(self) -> bool:
        return bool(
            self.oss_endpoint.strip()
            and self.oss_bucket.strip()
            and self.oss_access_key_id.strip()
            and self.oss_access_key_secret.strip()
        )

    @property
    def shop_hosts_list(self) -> list[str]:
        return [host.strip().lower() for host in self.shop_hosts.split(",") if host.strip()]

    @property
    def shop_contact(self) -> str:
        return self.shop_contact_email.strip() or self.initial_admin_email.strip() or "hello@carbonauten.com"

    @property
    def shop_stripe_configured(self) -> bool:
        return bool(self.shop_stripe_secret_key.strip())

    @property
    def shop_turnstile_configured(self) -> bool:
        return bool(self.shop_turnstile_site_key.strip() and self.shop_turnstile_secret_key.strip())

    @property
    def shop_public_origin(self) -> str:
        # Prefer first shop host when app_public_url is the platform domain
        hosts = self.shop_hosts_list
        if hosts:
            return f"https://{hosts[0]}"
        return self.effective_public_origin or "https://fuckco2.shop"

    @property
    def sync_configured(self) -> bool:
        return bool(self.sync_peer_url.strip() and self.sync_api_key.strip())

    @property
    def ai_search_configured(self) -> bool:
        if self.azure_openai_endpoint.strip() and self.azure_openai_api_key.strip():
            return bool(self.azure_openai_deployment.strip())
        return bool(self.openai_api_key.strip())

    @property
    def effective_database_url(self) -> str:
        url = (self.database_url or "").strip()
        if not url:
            url = "sqlite:///./data/content_hub.db"
        return ensure_postgres_ssl(normalize_database_url(url))


@lru_cache
def get_settings() -> Settings:
    return Settings()
