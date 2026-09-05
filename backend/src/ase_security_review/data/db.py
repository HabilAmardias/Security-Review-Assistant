"""SQLAlchemy engine + session factory for the SQLite metadata/audit DB."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_db_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    return engine


def init_db(engine: Engine) -> None:
    from . import models  # noqa: F401  (registers tables on Base.metadata)

    Base.metadata.create_all(engine)
    _migrate(engine)


# Columns added after a table's first release. Existing SQLite databases are
# missing them; `create_all` won't add columns, so we ALTER TABLE here. New
# databases already contain every column and this is a no-op.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "reviews": {
        "frd_text": "TEXT",
        "nfrd_text": "TEXT",
        "rule_test_level": "VARCHAR(32)",
        "rule_engine_enabled": "INTEGER DEFAULT 1",
        "detected_exposure": "VARCHAR(32)",
        "exposure_override": "VARCHAR(32)",
        "change_scope_override": "VARCHAR(32)",
        "form_fields_json": "TEXT",
        "pipeline": "VARCHAR(16)",
        "current_stage": "VARCHAR(32)",
        "analysis_json": "TEXT",
        "diagram_paths_json": "TEXT",
    },
}


def _migrate(engine: Engine) -> None:
    with engine.connect() as conn:
        for table, columns in _MIGRATIONS.items():
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            for column, ddl in columns.items():
                if column not in existing:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
                    )
        conn.commit()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]):
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
