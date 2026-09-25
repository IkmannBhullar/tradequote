"""Tests for the liveness and readiness endpoints."""

from collections.abc import Iterator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import get_db_session


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    # Integration test: hits the real Postgres from docker-compose (or the
    # CI service container) using DATABASE_URL.
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_database_is_unreachable(
    app: FastAPI, client: TestClient
) -> None:
    # Port 1 on localhost has nothing listening, so connecting fails fast
    # with "connection refused". That simulates the database being down.
    dead_engine = create_engine(
        "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        connect_args={"connect_timeout": 2},
    )

    def broken_session() -> Iterator[Session]:
        with Session(dead_engine) as session:
            yield session

    # dependency_overrides swaps a dependency for this app instance only;
    # the router code under test is unchanged.
    app.dependency_overrides[get_db_session] = broken_session
    try:
        response = client.get("/health/ready")
    finally:
        dead_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
