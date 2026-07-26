from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import load_settings


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=4)
def engine_for_url(database_url: str):
    return create_engine(database_url, pool_pre_ping=True)


def get_engine():
    return engine_for_url(load_settings().database_url)


def alembic_config() -> Config:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", load_settings().database_url)
    return config


MIGRATION_LOCK_ID = 875_413_029


def has_migration_state(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text("select to_regclass('public.alembic_version') is not null")
        ).scalar()
    )


def has_existing_schema(connection: Connection) -> bool:
    return bool(
        connection.execute(
            text(
                "select to_regclass('public.users') is not null or to_regclass('public.devices') is not null"
            )
        ).scalar()
    )


def validate_unversioned_schema(connection: Connection) -> None:
    """Only stamp an unversioned database when it already matches the current model."""
    database = inspect(connection)
    missing: list[str] = []
    for table in Base.metadata.sorted_tables:
        if not database.has_table(table.name):
            missing.append(f"table {table.name}")
            continue
        actual_columns = {item["name"] for item in database.get_columns(table.name)}
        for column in table.columns:
            if column.name not in actual_columns:
                missing.append(f"column {table.name}.{column.name}")
    if missing:
        details = ", ".join(missing[:12])
        if len(missing) > 12:
            details += f" and {len(missing) - 12} more"
        raise RuntimeError(
            "Unversioned PostgreSQL schema is not compatible with this release: "
            f"{details}. Restore a backup or migrate from a supported release."
        )


def migrate_db() -> None:
    from . import models  # noqa: F401

    with get_engine().connect() as connection:
        connection.execute(
            text("select pg_advisory_lock(:lock_id)"), {"lock_id": MIGRATION_LOCK_ID}
        )
        connection.commit()
        config = alembic_config()
        config.attributes["connection"] = connection
        try:
            if has_migration_state(connection):
                connection.commit()
                command.upgrade(config, "head")
            elif has_existing_schema(connection):
                validate_unversioned_schema(connection)
                connection.commit()
                command.stamp(config, "head")
            else:
                connection.commit()
                command.upgrade(config, "head")
        finally:
            if connection.in_transaction():
                connection.commit()
            connection.execute(
                text("select pg_advisory_unlock(:lock_id)"),
                {"lock_id": MIGRATION_LOCK_ID},
            )
            connection.commit()


def init_db() -> None:
    migrate_db()


def upgrade_db() -> None:
    migrate_db()


def check_database() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("select 1"))
    return True


def get_db() -> Generator[Session, None, None]:
    session_factory = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )
    with session_factory() as session:
        yield session
