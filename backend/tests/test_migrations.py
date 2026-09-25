"""Migration safety checks.

1. Round trip: the migrations can build the schema from nothing, tear it all
   down again, and rebuild it. A broken downgrade is found now, not during a
   stressful production rollback.
2. No drift: the models and the migrated database agree. This fails if
   someone changes a model but forgets to write a migration.
"""

from collections.abc import Iterator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, Engine, create_engine, inspect
from sqlalchemy.pool import NullPool

from app.models import Base
from tests.database import TEST_DATABASE_URL, downgrade, drop_database, migrate, recreate_database

# A separate throwaway database: the shared test database must stay at "head"
# for all the other tests.
SCRATCH_URL = TEST_DATABASE_URL.set(database=f"{TEST_DATABASE_URL.database}_migrations")


@pytest.fixture
def scratch_engine() -> Iterator[Engine]:
    recreate_database(SCRATCH_URL)
    engine = create_engine(SCRATCH_URL, poolclass=NullPool)
    yield engine
    engine.dispose()
    drop_database(SCRATCH_URL)


def test_upgrade_downgrade_upgrade_round_trip(scratch_engine: Engine) -> None:
    model_tables = set(Base.metadata.tables)

    with scratch_engine.begin() as connection:
        migrate(connection)
        # A fresh inspector each time: inspectors cache what they've seen.
        assert model_tables <= set(inspect(connection).get_table_names())

        downgrade(connection, "base")
        # Only Alembic's own bookkeeping table remains.
        assert inspect(connection).get_table_names() == ["alembic_version"]

        migrate(connection)
        assert model_tables <= set(inspect(connection).get_table_names())


def test_models_match_migrations(engine: Engine) -> None:
    # `engine` is the shared test database, already migrated to head.
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)

    assert differences == [], (
        "Models and migrations are out of sync. Run:\n"
        '  make migration name="describe your change"\n'
        f"Differences: {differences}"
    )


def test_check_constraints_match_models(engine: Engine) -> None:
    # Autogenerate (and so the test above) can't see CHECK constraints added
    # to existing tables, so a model CHECK missing from the migrations would
    # go unnoticed. Compare them by name instead.
    in_models = {
        str(constraint.name)
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    with engine.connect() as connection:
        inspector = inspect(connection)
        in_database = {
            str(check["name"])
            for table_name in inspector.get_table_names()
            for check in inspector.get_check_constraints(table_name)
        }

    assert in_models == in_database, (
        f"Only in models: {sorted(in_models - in_database)}\n"
        f"Only in database: {sorted(in_database - in_models)}"
    )
