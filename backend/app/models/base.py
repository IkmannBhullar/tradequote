"""Declarative base, shared column mixins, and type helpers for all models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Every constraint and index gets a deterministic name built from this pattern.
# Without it, Postgres invents names (e.g. "jobs_client_id_fkey"), and a future
# migration that needs to drop/alter a constraint can't reliably refer to it.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of every model. Its `metadata` is what Alembic compares
    against the database to generate migrations."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Python type -> column type defaults, so `Mapped[datetime]` always means a
    # timezone-aware column (never store naive timestamps).
    type_annotation_map = {  # noqa: RUF012  (SQLAlchemy reads this class attribute)
        datetime: DateTime(timezone=True),
    }


class UUIDPrimaryKeyMixin:
    # Generated in Python, so the id is known before the INSERT (handy for
    # building related rows in one go). UUIDs, unlike 1, 2, 3..., don't reveal
    # how many records exist and can't be guessed by incrementing.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    # server_default=now(): the database fills it, even for raw SQL inserts.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # onupdate fires on every ORM UPDATE. All writes go through repositories
    # (ORM), so we don't need a database trigger for this.
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class TenantMixin:
    """For tables owned by one organization (architecture rule 2).

    Repositories filter every query on this column. The index keeps those
    filters fast as the table grows.
    """

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )


def str_enum[E: enum.StrEnum](enum_cls: type[E], name: str) -> Enum:
    """Column type for a Python StrEnum, stored as VARCHAR + CHECK constraint.

    - native_enum=False: plain VARCHAR instead of a Postgres ENUM type, so
      adding a status later is an ordinary migration (design choice 2).
    - create_constraint=True: the database still rejects unknown values.
    - values_callable: store the enum's *value* ("draft"), not its Python
      member *name* ("DRAFT"), which is SQLAlchemy's surprising default.
    - `name` becomes the CHECK constraint name, e.g. ck_quotes_quote_status.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )
