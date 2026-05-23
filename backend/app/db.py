"""SQLite engine + session helpers.

The default path lives under `data/app.db` so it can be mounted as a Docker volume.
Override via the `DATABASE_URL` env var.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/app.db")


def _ensure_sqlite_dir(url: str) -> None:
    """Make sure the parent directory exists for sqlite file URLs."""
    if not url.startswith("sqlite"):
        return
    # forms: sqlite:///relative/path.db  or  sqlite:////absolute/path.db
    prefix, _, path = url.partition("sqlite:///")
    if not path:
        return
    db_path = Path(path)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(DATABASE_URL)

# check_same_thread=False so the engine can be reused across asyncio tasks.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


def init_db() -> None:
    """Create tables if they don't exist."""
    # Import models so SQLModel metadata is populated before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a Session."""
    with Session(engine) as session:
        yield session


def session_scope() -> Session:
    """Manual session for background tasks (caller must close)."""
    return Session(engine)
