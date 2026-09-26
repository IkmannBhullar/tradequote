"""Payments against a job, and the balance that drives "paid".

- What the client owes = the total of the job's latest APPROVED quote.
- Balance = owed - payments that aren't voided. It never goes below zero:
  a payment larger than the balance is rejected (catches typos; refunds and
  credits are out of scope).
- A job is PAID exactly when it's completed and its balance is zero. That
  one rule (settle_job_status) runs after every payment, every void, and
  every move to "completed", so the status always matches the money.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models import Job, Payment
from app.models.enums import JobStatus, PaymentKind
from app.repositories.jobs import JobRepository
from app.repositories.payments import PaymentRepository
from app.repositories.quotes import QuoteRepository
from app.services.context import Tenant
from app.services.errors import ConflictError, InvalidInputError, NotFoundError
from app.services.formatting import format_cents


@dataclass(frozen=True)
class PaymentSummary:
    # None until a quote is approved (nothing is owed yet).
    amount_due_cents: int | None
    paid_cents: int
    balance_cents: int | None
    deposit_required_cents: int | None
    deposit_outstanding_cents: int | None


@dataclass(frozen=True)
class JobPayments:
    job_status: JobStatus
    payments: list[Payment]
    summary: PaymentSummary


def _summary(session: Session, organization_id: uuid.UUID, job_id: uuid.UUID) -> PaymentSummary:
    paid = PaymentRepository(session, organization_id).paid_cents(job_id)
    quote = QuoteRepository(session, organization_id).latest_approved_for_job(job_id)
    if quote is None:
        return PaymentSummary(None, paid, None, None, None)
    return PaymentSummary(
        amount_due_cents=quote.total_cents,
        paid_cents=paid,
        balance_cents=quote.total_cents - paid,
        deposit_required_cents=quote.deposit_required_cents,
        deposit_outstanding_cents=max(quote.deposit_required_cents - paid, 0),
    )


def settle_job_status(session: Session, organization_id: uuid.UUID, job: Job) -> None:
    """Completed + fully paid = paid; paid with money owing again = completed.

    Only jobs that are completed or paid are touched: a job that's paid in
    full before the work is done becomes "paid" when it's marked completed.
    """
    if job.status not in (JobStatus.COMPLETED, JobStatus.PAID):
        return
    summary = _summary(session, organization_id, job.id)
    fully_paid = summary.balance_cents == 0
    job.status = JobStatus.PAID if fully_paid else JobStatus.COMPLETED


def _job(session: Session, tenant: Tenant, job_id: uuid.UUID, *, lock: bool = False) -> Job:
    jobs = JobRepository(session, tenant.organization_id)
    job = jobs.get_for_update(job_id) if lock else jobs.get(job_id)
    if job is None:
        raise NotFoundError("Job")
    return job


def _result(session: Session, tenant: Tenant, job: Job) -> JobPayments:
    return JobPayments(
        job_status=job.status,
        payments=list(PaymentRepository(session, tenant.organization_id).for_job(job.id)),
        summary=_summary(session, tenant.organization_id, job.id),
    )


def get_job_payments(session: Session, tenant: Tenant, job_id: uuid.UUID) -> JobPayments:
    return _result(session, tenant, _job(session, tenant, job_id))


def record_payment(
    session: Session,
    tenant: Tenant,
    job_id: uuid.UUID,
    *,
    amount_cents: int,
    kind: PaymentKind,
    method: str | None,
    received_on: date,
    today: date,
) -> JobPayments:
    # Locked: concurrent payments on this job run one at a time.
    job = _job(session, tenant, job_id, lock=True)
    summary = _summary(session, tenant.organization_id, job.id)
    if summary.balance_cents is None:
        raise ConflictError("Payments can be recorded once the job has an approved quote")
    if received_on > today:
        raise InvalidInputError("The payment date can't be in the future")
    if amount_cents > summary.balance_cents:
        raise InvalidInputError(
            f"That's more than the remaining balance of {format_cents(summary.balance_cents)}"
        )

    PaymentRepository(session, tenant.organization_id).add(
        Payment(
            job_id=job.id,
            amount_cents=amount_cents,
            kind=kind,
            method=method,
            received_on=received_on,
        )
    )
    settle_job_status(session, tenant.organization_id, job)
    session.commit()
    return _result(session, tenant, job)


def void_payment(
    session: Session, tenant: Tenant, job_id: uuid.UUID, payment_id: uuid.UUID, *, reason: str
) -> JobPayments:
    job = _job(session, tenant, job_id, lock=True)
    payment = PaymentRepository(session, tenant.organization_id).get(payment_id)
    # A payment on another job (or another org) is simply "not found".
    if payment is None or payment.job_id != job.id:
        raise NotFoundError("Payment")
    if payment.is_voided:
        raise ConflictError("This payment has already been voided")

    payment.voided_at = datetime.now(UTC)
    payment.void_reason = reason
    session.flush()
    # A paid job with money owing again goes back to "completed".
    settle_job_status(session, tenant.organization_id, job)
    session.commit()
    return _result(session, tenant, job)
