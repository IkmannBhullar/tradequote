"""Payment request/response shapes."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models.enums import JobStatus, PaymentKind
from app.schemas.common import ShortText
from app.services.payments import JobPayments


class PaymentCreate(BaseModel):
    amount_cents: Annotated[int, Field(gt=0, le=10**13)]
    kind: PaymentKind
    method: ShortText | None = None  # e.g. "e-transfer", "cheque", "cash"
    received_on: date  # a calendar date, e.g. "2026-09-25"


class VoidRequest(BaseModel):
    # Required: an audit trail should say why money was un-counted.
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=2000)]


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_cents: int
    kind: PaymentKind
    method: str | None
    received_on: date
    voided_at: datetime | None
    void_reason: str | None
    created_at: datetime


class PaymentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount_due_cents: int | None
    paid_cents: int
    balance_cents: int | None
    deposit_required_cents: int | None
    deposit_outstanding_cents: int | None


class JobPaymentsOut(BaseModel):
    job_status: JobStatus
    payments: list[PaymentOut]
    summary: PaymentSummaryOut
    # Today's date in the business's timezone: the latest allowed payment
    # date. Clients use it instead of their own clock, which may be in
    # another timezone (a UTC server at 10pm in New York is already on
    # tomorrow).
    today: date

    @classmethod
    def from_result(cls, result: JobPayments, *, today: date) -> "JobPaymentsOut":
        return cls(
            today=today,
            job_status=result.job_status,
            payments=[PaymentOut.model_validate(payment) for payment in result.payments],
            summary=PaymentSummaryOut.model_validate(result.summary),
        )
