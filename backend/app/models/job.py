"""Job: one piece of work for a client, tracked from quote to paid."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantScopedModel, str_enum
from app.models.enums import JobStatus

if TYPE_CHECKING:  # imported only for type checking, avoiding a circular import
    from app.models.client import Client


class Job(TenantScopedModel):
    __tablename__ = "jobs"
    __table_args__ = (
        # Composite FK = tenant safety net: the (org, client) pair must exist
        # in clients, so a job can never point at another org's client, even
        # if application code has a bug.
        ForeignKeyConstraint(
            ["organization_id", "client_id"],
            ["clients.organization_id", "clients.id"],
            ondelete="RESTRICT",
        ),
        # Lets quotes and payments use the same composite-FK trick on jobs.
        UniqueConstraint("organization_id", "id"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Optional: often the same as the client's address.
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), server_default=JobStatus.QUOTED.value
    )

    # Read-only link to the client, for showing its name. viewonly=True
    # because the composite foreign key above already manages client_id and
    # organization_id; a writable relationship would also try to set them.
    client: Mapped["Client"] = relationship(
        primaryjoin="foreign(Job.client_id) == Client.id", viewonly=True
    )

    @property
    def client_name(self) -> str:
        return self.client.name
