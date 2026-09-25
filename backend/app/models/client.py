"""Client: a contractor's customer (the homeowner/business receiving quotes)."""

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedModel


class Client(TenantScopedModel):
    __tablename__ = "clients"
    __table_args__ = (
        # `id` is already unique, so this looks redundant, but a foreign key
        # can only point at columns with a unique constraint. It lets jobs use a
        # composite FK (organization_id, client_id) that guarantees a job and
        # its client belong to the same organization.
        UniqueConstraint("organization_id", "id"),
    )

    name: Mapped[str] = mapped_column(String(200))
    # Only the name is required; contact details are often collected later.
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(Text)
