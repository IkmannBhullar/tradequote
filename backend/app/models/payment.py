"""Payment: money received for a job (a deposit or the final payment).

Payments are never edited or deleted. A mistaken one is VOIDED: it stays in
the history with a reason, and stops counting toward what's been paid. Money
records keep an audit trail.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantScopedModel, str_enum
from app.models.enums import PaymentKind


class Payment(TenantScopedModel):
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
        # (M7) Voided means both when and why; a void without a reason (or a
        # reason without a void) would be a bug.
        CheckConstraint("(voided_at IS NULL) = (void_reason IS NULL)", name="void_recorded"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[PaymentKind] = mapped_column(str_enum(PaymentKind, "payment_kind"))
    # Free text for now ("e-transfer", "cheque", "cash").
    method: Mapped[str | None] = mapped_column(String(50))
    # (M7) A calendar DATE, not a timestamp: "the cheque came on Sep 25" has
    # no time or timezone, and storing it as a UTC timestamp could shift it
    # to the 26th.
    received_on: Mapped[date]
    # (M7) Set when the payment is voided (it then no longer counts).
    voided_at: Mapped[datetime | None]
    void_reason: Mapped[str | None] = mapped_column(Text)

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None
