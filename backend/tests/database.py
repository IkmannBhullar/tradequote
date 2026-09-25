"""Test database helpers.

Importing this module points the app at a separate test database
(`<your dev db>_test`), so running tests never touches data you created while
using `make dev`. It must be imported before anything calls get_settings(),
which is why conftest.py imports it first.
"""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import URL, Connection, Engine, create_engine, make_url, text
from sqlalchemy.pool import NullPool

from app.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _derive_test_url() -> URL:
    dev_url = make_url(get_settings().database_url)
    name = dev_url.database or "tradequote"
    return dev_url if name.endswith("_test") else dev_url.set(database=f"{name}_test")


TEST_DATABASE_URL = _derive_test_url()

# Redirect the whole app (settings -> engine -> sessions) to the test database.
# render_as_string(hide_password=False): str(url) would mask the password.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL.render_as_string(hide_password=False)
os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()


def _admin_engine(url: URL) -> Engine:
    # CREATE/DROP DATABASE can't run inside a transaction, hence AUTOCOMMIT.
    # We connect to the built-in "postgres" database to manage the others.
    return create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )


def recreate_database(url: URL) -> None:
    """Drop (if present) and create an empty database at `url`."""
    name = url.database
    # Safety net: never let a misconfiguration drop a real database.
    assert name and "_test" in name, f"Refusing to recreate non-test database {name!r}"
    engine = _admin_engine(url)
    with engine.connect() as connection:
        # WITH (FORCE) disconnects leftover sessions (e.g. from a crashed run).
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine.dispose()


def drop_database(url: URL) -> None:
    name = url.database
    assert name and "_test" in name, f"Refusing to drop non-test database {name!r}"
    engine = _admin_engine(url)
    with engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    engine.dispose()


def alembic_config(connection: Connection) -> Config:
    """Alembic config that runs migrations on `connection` (see alembic/env.py)."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


def migrate(connection: Connection, revision: str = "head") -> None:
    command.upgrade(alembic_config(connection), revision)


def downgrade(connection: Connection, revision: str) -> None:
    command.downgrade(alembic_config(connection), revision)
