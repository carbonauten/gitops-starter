from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from app.database import BASELINE_REVISION, Base, _alembic_config, run_migrations


def _fresh_engine(tmp_path, name="migrations_test.db"):
    db_path = tmp_path / name
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)


def _current_version(engine) -> str:
    with engine.connect() as connection:
        return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()


def _head_revision() -> str:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def test_run_migrations_on_fresh_database_creates_all_tables_and_stamps_head(tmp_path):
    engine = _fresh_engine(tmp_path)
    run_migrations(engine)

    inspector = sa_inspect(engine)
    assert inspector.has_table("alembic_version")
    for table in Base.metadata.sorted_tables:
        assert inspector.has_table(table.name)

    assert _current_version(engine) == _head_revision()


def test_run_migrations_is_idempotent(tmp_path):
    engine = _fresh_engine(tmp_path, "idempotent.db")
    run_migrations(engine)
    run_migrations(engine)

    assert _current_version(engine) == _head_revision()


def test_run_migrations_stamps_baseline_for_pre_alembic_database(tmp_path):
    """Simulates a database that already has the baseline-era schema (every
    deployment up through the Alembic retrofit itself) but no alembic_version
    table yet, as opposed to one that already ran migrations before. Built by
    running only the baseline migration and then dropping the version table
    Alembic just created - Base.metadata.create_all() would instead stamp out
    today's full model shape (including columns added by later migrations),
    which is not what a database that predates those migrations looks like."""
    from alembic import command

    engine = _fresh_engine(tmp_path, "pre_alembic.db")
    cfg = _alembic_config()
    with engine.connect() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, BASELINE_REVISION)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")

    inspector = sa_inspect(engine)
    assert not inspector.has_table("alembic_version")

    run_migrations(engine)

    inspector = sa_inspect(engine)
    assert inspector.has_table("alembic_version")
    assert _current_version(engine) == _head_revision()
