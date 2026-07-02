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
    storage_path: Mapped[str] = mapped_column(String(1000))
    uploaded_by_id: Mapped[str] = mapped_column(String(100))
    uploaded_by_name: Mapped[str] = mapped_column(String(200))
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
    language: Mapped[str] = mapped_column(String(10), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50), default="compliance")
    issuer: Mapped[str] = mapped_column(String(500), default="")
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    renewal_in_progress: Mapped[bool] = mapped_column(Boolean, default=False)
    responsible_name: Mapped[str] = mapped_column(String(200), default="")
    responsible_email: Mapped[str] = mapped_column(String(200), default="")
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


def ensure_schema_updates(engine, is_sqlite: bool) -> None:
    inspector = sa_inspect(engine)
    if inspector.has_table("users"):
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "department_id" not in columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE users ADD COLUMN department_id VARCHAR(36)"))


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
