from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
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


def has_migration_state() -> bool:
    with get_engine().connect() as connection:
        return bool(
            connection.execute(
                text("select to_regclass('public.alembic_version') is not null")
            ).scalar()
        )


def has_existing_schema() -> bool:
    with get_engine().connect() as connection:
        return bool(
            connection.execute(
                text(
                    "select to_regclass('public.users') is not null or to_regclass('public.devices') is not null"
                )
            ).scalar()
        )


def migrate_db() -> None:
    from . import models  # noqa: F401

    if has_migration_state():
        command.upgrade(alembic_config(), "head")
        return

    if has_existing_schema():
        command.stamp(alembic_config(), "head")
        return

    command.upgrade(alembic_config(), "head")


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
