from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from app.database import BASELINE_REVISION, Base, run_migrations


def _fresh_engine(tmp_path, name="migrations_test.db"):
    db_path = tmp_path / name
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)


def _current_version(engine) -> str:
    with engine.connect() as connection:
        return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()


def test_run_migrations_on_fresh_database_creates_all_tables_and_stamps_head(tmp_path):
    engine = _fresh_engine(tmp_path)
    run_migrations(engine)

    inspector = sa_inspect(engine)
    assert inspector.has_table("alembic_version")
    for table in Base.metadata.sorted_tables:
        assert inspector.has_table(table.name)

    assert _current_version(engine) == BASELINE_REVISION


def test_run_migrations_is_idempotent(tmp_path):
    engine = _fresh_engine(tmp_path, "idempotent.db")
    run_migrations(engine)
    run_migrations(engine)

    assert _current_version(engine) == BASELINE_REVISION


def test_run_migrations_stamps_baseline_for_pre_alembic_database(tmp_path):
    """Every deployment before Alembic existed: tables were created by the old
    create_all() startup path, so they already exist but there is no
    alembic_version table yet."""
    engine = _fresh_engine(tmp_path, "pre_alembic.db")
    Base.metadata.create_all(engine)

    inspector = sa_inspect(engine)
    assert not inspector.has_table("alembic_version")

    run_migrations(engine)

    inspector = sa_inspect(engine)
    assert inspector.has_table("alembic_version")
    assert _current_version(engine) == BASELINE_REVISION
