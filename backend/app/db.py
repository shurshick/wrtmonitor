from collections.abc import Generator
from functools import lru_cache

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


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def check_database() -> bool:
    with get_engine().connect() as connection:
        connection.execute(text("select 1"))
    return True


def get_db() -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
