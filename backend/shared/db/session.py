"""Database sessions.

read_only()  → used by read_api. SQLite is opened with mode=ro, so any write raises an error.
read_write() → used by write_api only.
WAL journal mode lets readers and the single writer work at the same time.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from shared.config.settings import get_settings
from shared.db import models  # noqa: F401  (registers tables)


def _rw_engine(db_file: Path) -> Engine:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(conn, _):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    return engine


def _ro_engine(db_file: Path) -> Engine:
    return create_engine(
        f"sqlite:///file:{db_file}?mode=ro&uri=true",
        connect_args={"check_same_thread": False},
    )


@lru_cache
def write_engine(db_file: str | None = None) -> Engine:
    engine = _rw_engine(Path(db_file) if db_file else get_settings().db_file)
    SQLModel.metadata.create_all(engine)
    return engine


@lru_cache
def read_engine(db_file: str | None = None) -> Engine:
    path = Path(db_file) if db_file else get_settings().db_file
    if not path.exists():  # create an empty schema once so the read side can start first
        write_engine(str(path))
    return _ro_engine(path)


@contextmanager
def read_write(db_file: str | None = None) -> Iterator[Session]:
    with Session(write_engine(db_file)) as session:
        yield session


@contextmanager
def read_only(db_file: str | None = None) -> Iterator[Session]:
    with Session(read_engine(db_file)) as session:
        yield session
