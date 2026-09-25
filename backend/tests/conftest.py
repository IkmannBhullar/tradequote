"""Shared pytest fixtures.

pytest discovers this file automatically; any test can request a fixture
simply by naming it as a function parameter (e.g. `def test_x(client): ...`).
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    # A fresh app per test, so dependency overrides made in one test can
    # never leak into another.
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # TestClient calls the app in-process: no real server or port needed.
    # The `with` block runs the app's startup/shutdown events.
    with TestClient(app) as test_client:
        yield test_client
