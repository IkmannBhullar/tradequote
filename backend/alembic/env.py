"""Alembic environment: how Alembic connects to the database and which models
it compares against. Runs every time you invoke an `alembic` command.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.config import get_settings
from app.models import Base  # importing app.models registers every table

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: when tests run migrations in-process, we
    # must not silence the app's own loggers.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# The "desired" schema. `alembic revision --autogenerate` diffs this against
# the live database and writes the difference as a migration.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade --sql`: print the SQL instead of running it (useful for
    reviewing what a migration will do in production)."""
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Detect column type changes (e.g. String(50) -> String(100)) too.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Tests pass in their own connection (to a throwaway database) through
    # `config.attributes`; normal CLI usage builds one from DATABASE_URL.
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_with_connection(connection)
        return

    # NullPool: a one-off command doesn't need a connection pool. The URL is
    # passed straight to SQLAlchemy, never through configparser (see alembic.ini).
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
