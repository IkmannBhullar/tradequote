"""Job: one piece of work for a client, tracked from quote to paid."""

import uuid

from sqlalchemy import ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import JobStatus


class Job(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
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
