"""Database engine and session plumbing (SQLAlchemy 2.x, synchronous).

Two concepts:
- **Engine**: owns the connection *pool*. Expensive to create, so we make
  exactly one per process.
- **Session**: a short-lived unit of work (one per HTTP request). It borrows a
  connection from the pool and returns it when closed.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the engine lazily on first use (not at import time).

    Lazy creation means importing the app never needs a database, which keeps
    unit tests and tooling (mypy, ruff) independent of Postgres.
    """
    return create_engine(
        get_settings().database_url,
        # Before handing out a pooled connection, check it's still alive. This
        # avoids errors after Postgres restarts or drops idle connections.
        pool_pre_ping=True,
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    `yield` makes this a generator dependency. FastAPI runs the code before
    `yield` when the request starts and the cleanup (the `with` block exit)
    after the response is sent, even if the handler raised an exception.
    """
    with _session_factory()() as session:
        yield session
