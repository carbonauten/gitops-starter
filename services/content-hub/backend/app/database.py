from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator, Optional
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, create_engine, event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    template: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scheduled_publish_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[str] = mapped_column(String(100))
    author_name: Mapped[str] = mapped_column(String(200))
    author_email: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FileAsset(Base):
    __tablename__ = "file_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    original_name: Mapped[str] = mapped_column(String(500))
    stored_name: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(200), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    folder: Mapped[str] = mapped_column(String(200), default="general")
    folder_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    storage_path: Mapped[str] = mapped_column(String(1000))
    uploaded_by_id: Mapped[str] = mapped_column(String(100))
    uploaded_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FileFolder(Base):
    __tablename__ = "file_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserAccount(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entra_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30), default="editor")
    department_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class UserInvite(Base):
    __tablename__ = "user_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(200), index=True)
    role: Mapped[str] = mapped_column(String(30), default="editor")
    department_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    invited_by_id: Mapped[str] = mapped_column(String(100))
    invited_by_name: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PublishSettings(Base):
    __tablename__ = "publish_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: "default")
    teams_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    teams_team_id: Mapped[str] = mapped_column(String(100), default="")
    teams_channel_id: Mapped[str] = mapped_column(String(100), default="")
    outlook_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    outlook_sender_id: Mapped[str] = mapped_column(String(200), default="")
    notion_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    notion_database_id: Mapped[str] = mapped_column(String(100), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"

    provider: Mapped[str] = mapped_column(String(50), primary_key=True)
    access_token_enc: Mapped[str] = mapped_column(Text, default="")
    refresh_token_enc: Mapped[str] = mapped_column(Text, default="")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    account_label: Mapped[str] = mapped_column(String(300), default="")
    connected_by_id: Mapped[str] = mapped_column(String(100), default="")
    connected_by_name: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    resource_type: Mapped[str] = mapped_column(String(50), default="article")
    resource_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    published_by_id: Mapped[str] = mapped_column(String(100))
    published_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PublicationDelivery(Base):
    __tablename__ = "publication_deliveries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    publication_id: Mapped[str] = mapped_column(String(36), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50), default="compliance")
    issuer: Mapped[str] = mapped_column(String(500), default="")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    renewal_in_progress: Mapped[bool] = mapped_column(Boolean, default=False)
    renewal_approval_status: Mapped[str] = mapped_column(String(30), default="none")
    renewal_review_comment: Mapped[str] = mapped_column(Text, default="")
    responsible_name: Mapped[str] = mapped_column(String(200), default="")
    responsible_email: Mapped[str] = mapped_column(String(200), default="")
    escalate_email: Mapped[str] = mapped_column(String(200), default="")
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    reminder_90_sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reminder_60_sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    reminder_30_sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    file_asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[str] = mapped_column(String(100))
    created_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    direction: Mapped[str] = mapped_column(String(20), default="pull")
    status: Mapped[str] = mapped_column(String(20), default="success")
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    certificate_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    actor_id: Mapped[str] = mapped_column(String(100))
    actor_name: Mapped[str] = mapped_column(String(200))
    actor_email: Mapped[str] = mapped_column(String(200), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ContentRevision(Base):
    __tablename__ = "content_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    changed_by_id: Mapped[str] = mapped_column(String(100), default="")
    changed_by_name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


def scheduled_publish_column_type(is_sqlite: bool) -> str:
    return "DATETIME" if is_sqlite else "TIMESTAMP WITH TIME ZONE"


def ensure_schema_updates(engine, is_sqlite: bool) -> None:
    inspector = sa_inspect(engine)
    if inspector.has_table("users"):
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "department_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN department_id VARCHAR(36)"))
        if "password_hash" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
    if inspector.has_table("file_assets"):
        columns = {column["name"] for column in inspector.get_columns("file_assets")}
        if "folder_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE file_assets ADD COLUMN folder_id VARCHAR(36)"))
    if inspector.has_table("articles"):
        columns = {column["name"] for column in inspector.get_columns("articles")}
        scheduled_type = scheduled_publish_column_type(is_sqlite)
        if "scheduled_publish_at" not in columns:
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE articles ADD COLUMN scheduled_publish_at {scheduled_type}")
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not add articles.scheduled_publish_at: %s", exc)
        if "review_comment" not in columns:
            try:
                with engine.begin() as connection:
                    if is_sqlite:
                        connection.execute(text("ALTER TABLE articles ADD COLUMN review_comment TEXT DEFAULT ''"))
                    else:
                        connection.execute(
                            text("ALTER TABLE articles ADD COLUMN review_comment TEXT NOT NULL DEFAULT ''")
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not add articles.review_comment: %s", exc)
    if inspector.has_table("certificates"):
        columns = {column["name"] for column in inspector.get_columns("certificates")}
        if "renewal_approval_status" not in columns:
            with engine.begin() as connection:
                if is_sqlite:
                    connection.execute(
                        text(
                            "ALTER TABLE certificates ADD COLUMN renewal_approval_status VARCHAR(30) DEFAULT 'none'"
                        )
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE certificates ADD COLUMN renewal_approval_status VARCHAR(30) NOT NULL DEFAULT 'none'"
                        )
                    )
        if "renewal_review_comment" not in columns:
            with engine.begin() as connection:
                if is_sqlite:
                    connection.execute(
                        text("ALTER TABLE certificates ADD COLUMN renewal_review_comment TEXT DEFAULT ''")
                    )
                else:
                    connection.execute(
                        text(
                            "ALTER TABLE certificates ADD COLUMN renewal_review_comment TEXT NOT NULL DEFAULT ''"
                        )
                    )
        for column_name, ddl_sqlite, ddl_pg in (
            ("parent_id", "ALTER TABLE certificates ADD COLUMN parent_id VARCHAR(36)", "ALTER TABLE certificates ADD COLUMN parent_id VARCHAR(36)"),
            ("escalate_email", "ALTER TABLE certificates ADD COLUMN escalate_email VARCHAR(200) DEFAULT ''", "ALTER TABLE certificates ADD COLUMN escalate_email VARCHAR(200) NOT NULL DEFAULT ''"),
            ("reminder_90_sent_on", "ALTER TABLE certificates ADD COLUMN reminder_90_sent_on DATE", "ALTER TABLE certificates ADD COLUMN reminder_90_sent_on DATE"),
            ("reminder_60_sent_on", "ALTER TABLE certificates ADD COLUMN reminder_60_sent_on DATE", "ALTER TABLE certificates ADD COLUMN reminder_60_sent_on DATE"),
            ("reminder_30_sent_on", "ALTER TABLE certificates ADD COLUMN reminder_30_sent_on DATE", "ALTER TABLE certificates ADD COLUMN reminder_30_sent_on DATE"),
        ):
            if column_name not in columns:
                try:
                    with engine.begin() as connection:
                        connection.execute(text(ddl_sqlite if is_sqlite else ddl_pg))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not add certificates.%s: %s", column_name, exc)


DEFAULT_DEPARTMENTS: tuple[tuple[str, str, int], ...] = (
    ("IT", "it", 10),
    ("Marketing", "marketing", 20),
    ("Produktion", "production", 30),
    ("Vertrieb", "sales", 40),
    ("Verwaltung", "admin", 50),
)


def seed_default_departments(db: Session) -> None:
    existing = db.scalar(select(func.count()).select_from(Department)) or 0
    if existing:
        return
    for name, code, sort_order in DEFAULT_DEPARTMENTS:
        db.add(Department(name=name, code=code, sort_order=sort_order, is_active=True))
    db.commit()


def init_database(database_url: str, max_attempts: int = 10, retry_delay: float = 3.0) -> None:
    global _engine, _SessionLocal

    is_sqlite = database_url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine_kwargs = {"connect_args": connect_args, "future": True}
    if not is_sqlite:
        engine_kwargs["pool_pre_ping"] = True

    _engine = create_engine(database_url, **engine_kwargs)

    if is_sqlite:

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with _engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            Base.metadata.create_all(_engine)
            ensure_schema_updates(_engine, is_sqlite)
            _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, future=True)
            with _SessionLocal() as db:
                seed_default_departments(db)
                from .user_service import ensure_initial_admin

                ensure_initial_admin(db)
                from .file_folder_service import migrate_legacy_file_folders, seed_default_folders

                seed_default_folders(db)
                migrate_legacy_file_folders(db)
            logger.info("Database initialized")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == max_attempts:
                break
            logger.warning(
                "Database not ready (attempt %s/%s): %s",
                attempt,
                max_attempts,
                exc,
            )
            time.sleep(retry_delay)

    raise RuntimeError(f"Database connection failed after {max_attempts} attempts") from last_error


def reset_database() -> None:
    if _engine is not None:
        Base.metadata.drop_all(_engine)
        Base.metadata.create_all(_engine)


def get_db() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_upload_dir(upload_dir: str) -> Path:
    path = Path(upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path
