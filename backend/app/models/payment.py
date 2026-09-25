"""Payment: money received for a job (a deposit or the final payment)."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.models.enums import PaymentKind


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        # Tenant safety net: the job must belong to the same org.
        ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["jobs.organization_id", "jobs.id"],
            ondelete="RESTRICT",
        ),
        # A $0 payment is meaningless; refunds would be modeled separately.
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[PaymentKind] = mapped_column(str_enum(PaymentKind, "payment_kind"))
    # Free text for now ("e-transfer", "cheque", "cash").
    method: Mapped[str | None] = mapped_column(String(50))
    received_at: Mapped[datetime]
