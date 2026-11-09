from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection, Engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.database import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _resolve_url() -> str:
    from app.config import get_settings

    return get_settings().effective_database_url


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or _resolve_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")

    if connectable is None:
        url = config.get_main_option("sqlalchemy.url") or _resolve_url()
        configuration = config.get_section(config.config_ini_section) or {}
        configuration["sqlalchemy.url"] = url
        connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    if isinstance(connectable, Connection):
        context.configure(connection=connectable, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    assert isinstance(connectable, Engine)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
