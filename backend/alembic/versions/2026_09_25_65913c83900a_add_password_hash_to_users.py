"""add password hash to users

Adds a NOT NULL column with no default. That's only safe because no user rows
exist yet (users are first created by the sign-up flow added alongside this
migration). On a table with data, this would need three steps instead: add
the column as nullable, backfill it, then set NOT NULL.

Revision ID: 65913c83900a
Revises: a6e03b9abfbd
Create Date: 2026-09-25 16:11:41.633761

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision identifiers, used by Alembic to order migrations.
revision: str = "65913c83900a"
down_revision: str | Sequence[str] | None = "a6e03b9abfbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
