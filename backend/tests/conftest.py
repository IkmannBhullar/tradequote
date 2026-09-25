"""Shared pytest fixtures.

pytest discovers this file automatically; any test can request a fixture
simply by naming it as a function parameter (e.g. `def test_x(client): ...`).
"""

# Must come first: redirects DATABASE_URL to the test database before any
# app code reads settings.
from tests.database import TEST_DATABASE_URL, migrate, recreate_database  # isort: skip

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db import get_db_session, get_engine
from app.main import create_app


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A freshly created, fully migrated test database, built once per run.

    scope="session" means pytest builds it once and shares it between all
    tests. Migrating via Alembic (not Base.metadata.create_all) means the
    tests run against exactly the schema production will have.
    """
    recreate_database(TEST_DATABASE_URL)
    engine = get_engine()
    with engine.begin() as connection:
        migrate(connection)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose changes are always rolled back after the test.

    We open a real transaction on one connection and bind the session to it.
    join_transaction_mode="create_savepoint" turns the session's own
    commit()/rollback() into savepoint operations, so even code that commits
    can't make changes that outlive the test. Each test starts from the same
    clean, migrated database.
    """
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    # A fresh app per test, so dependency overrides made in one test can
    # never leak into another. Requests share the test's rolled-back session.
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # TestClient calls the app in-process: no real server or port needed.
    # The `with` block runs the app's startup/shutdown events.
    with TestClient(app) as test_client:
        yield test_client
