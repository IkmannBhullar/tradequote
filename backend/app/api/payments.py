"""Payment endpoints, nested under the job they belong to."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, status

from app.api.deps import AppSettings, CurrentTenant, DbSession
from app.config import Settings
from app.schemas.payments import JobPaymentsOut, PaymentCreate, VoidRequest
from app.services import payments as payment_service

router = APIRouter(prefix="/jobs/{job_id}/payments", tags=["payments"])


def _business_today(settings: Settings) -> date:
    # "Today" in the business's timezone: in a North American evening, UTC is
    # already tomorrow, and today's payment must not count as "in the future".
    return datetime.now(ZoneInfo(settings.display_timezone)).date()


@router.get("", response_model=JobPaymentsOut)
def list_payments(
    job_id: uuid.UUID, tenant: CurrentTenant, session: DbSession, settings: AppSettings
) -> JobPaymentsOut:
    """The job's payments (voided ones included, for the audit trail) and balance."""
    result = payment_service.get_job_payments(session, tenant, job_id)
    return JobPaymentsOut.from_result(result, today=_business_today(settings))


@router.post("", response_model=JobPaymentsOut, status_code=status.HTTP_201_CREATED)
def record_payment(
    job_id: uuid.UUID,
    body: PaymentCreate,
    tenant: CurrentTenant,
    session: DbSession,
    settings: AppSettings,
) -> JobPaymentsOut:
    today = _business_today(settings)
    result = payment_service.record_payment(
        session,
        tenant,
        job_id,
        amount_cents=body.amount_cents,
        kind=body.kind,
        method=body.method,
        received_on=body.received_on,
        today=today,
    )
    return JobPaymentsOut.from_result(result, today=today)


@router.post("/{payment_id}/void", response_model=JobPaymentsOut)
def void_payment(
    job_id: uuid.UUID,
    payment_id: uuid.UUID,
    body: VoidRequest,
    tenant: CurrentTenant,
    session: DbSession,
    settings: AppSettings,
) -> JobPaymentsOut:
    """Stop a mistaken payment from counting. It stays in the history."""
    result = payment_service.void_payment(session, tenant, job_id, payment_id, reason=body.reason)
    return JobPaymentsOut.from_result(result, today=_business_today(settings))
